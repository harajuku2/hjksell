"""Official Telegram Bot API integration and safe catalogue importing."""

from __future__ import annotations

import logging
import json
import re
import threading
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable

import httpx
from PySide6.QtCore import QObject, Signal, Slot

from ..database.models import Item
from ..repositories.item_repository import ItemRepository
from ..repositories.settings_repository import SettingsRepository
from ..repositories.telegram_repository import TelegramRepository
from .finance import parse_decimal
from .items import ItemService
from .photos import PhotoStorage

logger = logging.getLogger(__name__)
_CAPTION_RE = re.compile(r"^[0-9]+(?:[.,][0-9]{1,2})?$")


class TelegramApiError(RuntimeError):
    """A Telegram API failure whose message never contains the bot token."""


class TelegramApiClient:
    """Small httpx client for the Bot API; no send/reply methods are exposed."""

    def __init__(
        self,
        token: str,
        *,
        client: httpx.Client | None = None,
        api_root: str = "https://api.telegram.org",
    ) -> None:
        token = token.strip()
        if not token:
            raise ValueError("Введите токен Telegram.")
        self._token = token
        self._api_root = api_root.rstrip("/")
        self._client = client or httpx.Client(timeout=httpx.Timeout(55.0, connect=10.0), trust_env=False)
        self._owns_client = client is None
        # Bot API URLs contain the token; never allow transport debug logs to
        # print those URLs to a terminal or application log.
        for logger_name in ("httpx", "httpcore"):
            transport_logger = logging.getLogger(logger_name)
            transport_logger.setLevel(logging.WARNING)
            transport_logger.disabled = True

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def _call(self, method: str, **params: Any) -> Any:
        response = self._client.get(f"{self._api_root}/bot{self._token}/{method}", params=params)
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            if response.status_code == 401:
                raise TelegramApiError("Telegram отклонил токен бота.") from exc
            if response.status_code == 409:
                raise TelegramApiError(
                    "Telegram уже используется другим polling-процессом. Закройте desktop или другой Web-сервер."
                ) from exc
            raise TelegramApiError(f"Telegram API вернул HTTP {response.status_code}.") from exc
        try:
            payload = response.json()
        except ValueError as exc:
            raise TelegramApiError("Telegram вернул некорректный ответ.") from exc
        if not payload.get("ok"):
            description = str(payload.get("description") or "Запрос Telegram не выполнен.")
            raise TelegramApiError(description[:300])
        return payload.get("result")

    def get_me(self) -> dict[str, Any]:
        result = self._call("getMe")
        return result if isinstance(result, dict) else {}

    def validate_token(self) -> dict[str, Any]:
        """Validate credentials using the official getMe endpoint."""

        return self.get_me()

    def get_updates(self, offset: int | None = None, timeout: int = 50) -> list[dict[str, Any]]:
        params: dict[str, Any] = {
            "timeout": max(0, min(50, timeout)),
            "allowed_updates": json.dumps(["channel_post"]),
        }
        if offset is not None:
            params["offset"] = offset
        result = self._call("getUpdates", **params)
        return result if isinstance(result, list) else []

    def download_photo(self, file_id: str) -> tuple[bytes, str]:
        file_info = self._call("getFile", file_id=file_id)
        if not isinstance(file_info, dict) or not file_info.get("file_path"):
            raise TelegramApiError("Telegram не вернул путь к фото.")
        file_path = str(file_info["file_path"])
        response = self._client.get(f"{self._api_root}/file/bot{self._token}/{file_path}")
        response.raise_for_status()
        suffix = Path(file_path).suffix.lower() or ".jpg"
        return response.content, suffix


@dataclass(frozen=True)
class ParsedChannelPost:
    update_id: int
    channel_id: str
    title: str | None
    message_id: int
    photo_file_id: str
    price_pln: str
    purchase_date: date


@dataclass(frozen=True)
class ImportDiagnostic:
    update_id: int | None
    status: str
    message: str
    channel_id: str | None = None


def parse_channel_post(update: dict[str, Any]) -> ParsedChannelPost:
    """Parse the deliberately strict one-photo-plus-number post format."""

    if not isinstance(update, dict) or not isinstance(update.get("update_id"), int):
        raise ValueError("У сообщения отсутствует update_id.")
    message = update.get("channel_post")
    if not isinstance(message, dict):
        raise ValueError("Это не публикация канала.")
    if message.get("media_group_id") is not None:
        raise ValueError("Альбомы Telegram не поддерживаются.")
    chat = message.get("chat")
    if not isinstance(chat, dict) or chat.get("id") is None:
        raise ValueError("У публикации отсутствует канал.")
    photos = message.get("photo")
    if not isinstance(photos, list) or not photos:
        raise ValueError("Нужна ровно одна фотография.")
    # Telegram represents one photo as several sizes.  A media group is rejected above.
    photo = photos[-1]
    if not isinstance(photo, dict) or not photo.get("file_id"):
        raise ValueError("Фото Telegram недоступно.")
    caption = message.get("caption")
    if not isinstance(caption, str):
        raise ValueError("Подпись должна содержать цену PLN.")
    normalized_caption = re.sub(r"\s*([.,])\s*", r"\1", caption.strip()).replace(",", ".")
    if not _CAPTION_RE.fullmatch(normalized_caption):
        raise ValueError("Цена должна быть числом, например 150 или 150,50.")
    price = parse_decimal(normalized_caption, field_name="цену PLN", non_negative=True)
    if price.as_tuple().exponent < -2:
        raise ValueError("Цена может содержать не более двух знаков после запятой.")
    timestamp = message.get("date")
    if not isinstance(timestamp, (int, float)):
        raise ValueError("У публикации отсутствует дата.")
    return ParsedChannelPost(
        update_id=update["update_id"],
        channel_id=str(chat["id"]),
        title=str(chat["title"])[:255] if chat.get("title") else None,
        message_id=int(message["message_id"]),
        photo_file_id=str(photo["file_id"]),
        price_pln=str(price),
        purchase_date=datetime.fromtimestamp(timestamp).date(),
    )


parse_telegram_update = parse_channel_post


class TelegramImportService:
    """Import updates in one database transaction per update."""

    def __init__(
        self,
        session_factory: Callable,
        photo_service: PhotoStorage,
        api: TelegramApiClient,
        portfolio_id: int = 1,
        *,
        scope_discoveries: bool = False,
    ) -> None:
        self.session_factory = session_factory
        self.photo_service = photo_service
        self.api = api
        self.portfolio_id = portfolio_id
        self.scope_discoveries = scope_discoveries
        self.diagnostics: list[ImportDiagnostic] = []
        self.discovered_channels: list[tuple[str, str | None]] = []

    def _diagnostic(self, value: ImportDiagnostic) -> None:
        self.diagnostics.append(value)
        del self.diagnostics[:-100]
        logger.warning("Telegram update %s: %s", value.update_id, value.message)

    def import_update(self, update: dict[str, Any]) -> ImportDiagnostic:
        update_id = update.get("update_id") if isinstance(update, dict) else None
        try:
            parsed = parse_channel_post(update)
        except (ValueError, TypeError, KeyError) as exc:
            if isinstance(update, dict) and isinstance(update.get("update_id"), int):
                with self.session_factory() as session:
                    repository = TelegramRepository(session)
                    repository.record_diagnostic(update["update_id"], "ignored", str(exc), self.portfolio_id)
                    repository.set_offset(self.portfolio_id, update["update_id"] + 1)
                    session.commit()
            result = ImportDiagnostic(update_id, "ignored", str(exc))
            self._diagnostic(result)
            return result

        photo_path: str | None = None
        try:
            with self.session_factory() as session:
                telegram = TelegramRepository(session)
                if telegram.has_import(self.portfolio_id, parsed.channel_id, parsed.message_id, parsed.update_id):
                    telegram.set_offset(self.portfolio_id, parsed.update_id + 1)
                    session.commit()
                    result = ImportDiagnostic(parsed.update_id, "duplicate", "Дубликат уже импортирован.", parsed.channel_id)
                    self._diagnostic(result)
                    return result
                channel = telegram.channel(parsed.channel_id, self.portfolio_id)
                if channel is None or not channel.is_bound or channel.portfolio_id is None:
                    if (parsed.channel_id, parsed.title) not in self.discovered_channels:
                        self.discovered_channels.append((parsed.channel_id, parsed.title))
                    telegram.record_discovered_channel(
                        parsed.channel_id,
                        parsed.title,
                        self.portfolio_id if self.scope_discoveries else None,
                    )
                    telegram.record_diagnostic(
                        parsed.update_id,
                        "ignored",
                        "Канал не привязан.",
                        self.portfolio_id,
                        parsed.channel_id,
                        parsed.message_id,
                    )
                    telegram.set_offset(self.portfolio_id, parsed.update_id + 1)
                    session.commit()
                    result = ImportDiagnostic(parsed.update_id, "ignored", "Канал не привязан.", parsed.channel_id)
                    self._diagnostic(result)
                    return result
                content, suffix = self.api.download_photo(parsed.photo_file_id)
                photo_path = self.photo_service.save_photo_bytes(content, suffix)
                item = ItemService(ItemRepository(session), SettingsRepository(session)).create_from_text(
                    channel.portfolio_id,
                    parsed.price_pln,
                    parsed.purchase_date,
                    photo_path,
                )
                item.telegram_channel_id = parsed.channel_id
                item.telegram_message_id = parsed.message_id
                item.telegram_update_id = parsed.update_id
                telegram.record_import(self.portfolio_id, parsed.channel_id, parsed.message_id, parsed.update_id)
                telegram.set_offset(self.portfolio_id, parsed.update_id + 1)
                session.commit()
            result = ImportDiagnostic(parsed.update_id, "imported", "Покупка добавлена.", parsed.channel_id)
            self._diagnostic(result)
            return result
        except Exception as exc:
            if photo_path:
                try:
                    Path(photo_path).unlink(missing_ok=True)
                except OSError:
                    pass
            if isinstance(update, dict) and isinstance(update.get("update_id"), int):
                with self.session_factory() as diagnostic_session:
                    TelegramRepository(diagnostic_session).record_diagnostic(
                        update["update_id"],
                        "error",
                        _safe_error(exc),
                        self.portfolio_id,
                        parsed.channel_id,
                        parsed.message_id,
                    )
                    diagnostic_session.commit()
            # Do not advance the offset: transient network/database errors are retryable.
            result = ImportDiagnostic(parsed.update_id, "error", _safe_error(exc), parsed.channel_id)
            self._diagnostic(result)
            return result

    def poll_once(self) -> list[ImportDiagnostic]:
        with self.session_factory() as session:
            token = TelegramRepository(session).token(self.portfolio_id)
            offset = TelegramRepository(session).offset(self.portfolio_id)
        if not token:
            result = ImportDiagnostic(None, "error", "Токен Telegram не настроен.")
            self._diagnostic(result)
            return [result]
        updates = self.api.get_updates(offset=offset, timeout=50)
        return [self.import_update(update) for update in updates]

    def stop(self) -> None:
        """Cancel an active long poll by closing its client connection."""

        self.api.close()


def _safe_error(exc: Exception) -> str:
    """Keep diagnostics useful without ever echoing credentials or request URLs."""

    if isinstance(exc, TelegramApiError):
        return str(exc)[:300]
    if isinstance(exc, httpx.ConnectError):
        return "Не удалось подключиться к Telegram API. Проверьте интернет-соединение или настройки сети."
    if isinstance(exc, httpx.NetworkError):
        return "Сетевое соединение с Telegram API прервано. Повторяю проверку автоматически."
    if isinstance(exc, httpx.TimeoutException):
        return "Telegram API не ответил вовремя. Проверьте интернет-соединение."
    return f"Ошибка импорта: {type(exc).__name__}."


class TelegramWorker:
    """Thread-friendly polling worker; the lock prevents overlapping polls."""

    def __init__(self, importer: TelegramImportService, interval_seconds: float = 50.0) -> None:
        self.importer = importer
        self.interval_seconds = interval_seconds
        self._poll_lock = threading.Lock()
        self._stop = threading.Event()
        self._wake = threading.Event()

    def poll_once(self) -> list[ImportDiagnostic]:
        if not self._poll_lock.acquire(blocking=False):
            return []
        try:
            return self.importer.poll_once()
        finally:
            self._poll_lock.release()

    run_once = poll_once

    def run(self, callback: Callable[[list[ImportDiagnostic]], None] | None = None) -> None:
        while not self._stop.is_set():
            try:
                diagnostics = self.poll_once()
                if callback:
                    callback(diagnostics)
                # getUpdates itself is the ~50-second long poll.  Start the next
                # request immediately instead of adding another 50-second sleep.
                if any(getattr(value, "status", "") == "error" for value in diagnostics):
                    self._wake.wait(self.interval_seconds)
                    self._wake.clear()
            except Exception as exc:
                diagnostic = ImportDiagnostic(None, "error", _safe_error(exc))
                self.importer._diagnostic(diagnostic)
                if callback:
                    callback([diagnostic])
                self._wake.wait(self.interval_seconds)
                self._wake.clear()
            self._wake.clear()

    def stop(self) -> None:
        self._stop.set()
        self._wake.set()
        stop = getattr(self.importer, "stop", None)
        if callable(stop):
            stop()

    def request_poll(self) -> None:
        """Wake the long-poll loop for the manual ↻ Telegram action."""

        self._wake.set()


class TelegramQtWorker(QObject):
    """QObject adapter used by the desktop UI's dedicated QThread."""

    diagnostics = Signal(int, object)
    finished = Signal()

    def __init__(self, importer: TelegramImportService, interval_seconds: float = 50.0) -> None:
        super().__init__()
        self.worker = TelegramWorker(importer, interval_seconds)

    @Slot()
    def run(self) -> None:
        try:
            self.worker.run(self._emit_diagnostics)
        finally:
            self.finished.emit()

    @Slot(object)
    def _emit_diagnostics(self, values: list[ImportDiagnostic]) -> None:
        self.diagnostics.emit(self.worker.importer.portfolio_id, values)

    def request_poll(self) -> None:
        self.worker.request_poll()

    def stop(self) -> None:
        self.worker.stop()


class TelegramValidationWorker(QObject):
    """Run getMe off the GUI thread."""

    finished = Signal(bool, str)

    def __init__(self, token: str) -> None:
        super().__init__()
        self.token = token

    @Slot()
    def run(self) -> None:
        client: TelegramApiClient | None = None
        try:
            client = TelegramApiClient(self.token)
            me = client.get_me()
            name = str(me.get("username") or me.get("first_name") or "бот")
            self.finished.emit(True, f"Подключено: @{name}" if me.get("username") else f"Подключено: {name}")
        except Exception as exc:
            self.finished.emit(False, _safe_error(exc))
        finally:
            if client:
                client.close()


# Short aliases make the service convenient for callers and tests.
TelegramService = TelegramImportService
TelegramPollingWorker = TelegramWorker

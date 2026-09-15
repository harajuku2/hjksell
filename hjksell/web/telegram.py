"""Web-owned Telegram polling orchestration over the shared import service."""

from __future__ import annotations

import threading
from dataclasses import dataclass

from ..config import AppPaths
from ..repositories.portfolio_repository import PortfolioRepository
from ..repositories.telegram_repository import TelegramRepository
from ..services.photos import PhotoService
from ..services.telegram import ImportDiagnostic, TelegramApiClient, TelegramImportService, TelegramWorker


@dataclass
class _RunningPoller:
    worker: TelegramWorker
    thread: threading.Thread


class WebTelegramManager:
    """Own one cooperative polling worker per configured portfolio.

    The manager intentionally contains no import or financial rules. It only
    wires the existing Telegram API, importer, and local photo storage to the
    Web application's lifecycle.
    """

    def __init__(self, session_factory, paths: AppPaths) -> None:
        self.session_factory = session_factory
        self.photo_service = PhotoService(paths)
        self._pollers: dict[int, _RunningPoller] = {}
        self._last_diagnostics: dict[int, list[ImportDiagnostic]] = {}
        self._lock = threading.RLock()
        self._lifecycle_lock = threading.Lock()

    def start(self) -> None:
        with self.session_factory() as session:
            portfolio_ids = [portfolio.id for portfolio in PortfolioRepository(session).list_all()]
        for portfolio_id in portfolio_ids:
            self.reconfigure(portfolio_id)

    def stop(self) -> None:
        with self._lifecycle_lock:
            with self._lock:
                pollers = list(self._pollers.values())
                self._pollers.clear()
            for poller in pollers:
                poller.worker.stop()
            for poller in pollers:
                poller.thread.join(timeout=3)

    def reconfigure(self, portfolio_id: int) -> None:
        with self._lifecycle_lock:
            with self._lock:
                self._last_diagnostics.pop(portfolio_id, None)
            self._stop_portfolio(portfolio_id)
            with self.session_factory() as session:
                token = TelegramRepository(session).token(portfolio_id)
            if not token:
                return

            api = TelegramApiClient(token)
            importer = TelegramImportService(self.session_factory, self.photo_service, api, portfolio_id)
            worker = TelegramWorker(importer, interval_seconds=50.0)
            thread = threading.Thread(
                target=worker.run,
                args=(lambda values, current_id=portfolio_id, current_worker=worker: self._remember(
                    current_id, current_worker, values
                ),),
                name=f"telegram-web-{portfolio_id}",
                daemon=True,
            )
            with self._lock:
                self._pollers[portfolio_id] = _RunningPoller(worker, thread)
            thread.start()

    def status(self, portfolio_id: int) -> dict:
        with self.session_factory() as session:
            repository = TelegramRepository(session)
            token = repository.token(portfolio_id)
            channels = [channel for channel in repository.channels() if channel.portfolio_id == portfolio_id]
            discovered = repository.discovered_channels() if token else []
            offset = repository.offset(portfolio_id)
        with self._lock:
            poller = self._pollers.get(portfolio_id)
            diagnostics = list(self._last_diagnostics.get(portfolio_id, []))
        last = diagnostics[-1] if diagnostics else None
        return {
            "configured": bool(token and channels),
            "running": bool(poller and poller.thread.is_alive()),
            "channel_id": channels[0].channel_id if channels else None,
            "channel_title": channels[0].title if channels else None,
            "offset": offset,
            "last_status": last.status if last else None,
            "last_message": last.message if last else None,
            "discovered_channels": [
                {"channel_id": channel.channel_id, "title": channel.title}
                for channel in discovered
            ],
        }

    def _remember(self, portfolio_id: int, worker: TelegramWorker, values: list[ImportDiagnostic]) -> None:
        with self._lock:
            poller = self._pollers.get(portfolio_id)
            if poller is None or poller.worker is not worker:
                return
            self._last_diagnostics[portfolio_id] = list(values)[-20:]

    def _stop_portfolio(self, portfolio_id: int) -> None:
        with self._lock:
            poller = self._pollers.pop(portfolio_id, None)
        if poller is None:
            return
        poller.worker.stop()
        poller.thread.join(timeout=3)

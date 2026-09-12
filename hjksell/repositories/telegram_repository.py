"""Persistence helpers for Telegram bindings, offsets, and imports."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..database.models import TelegramChannel, TelegramImport


OFFSET_KEY = "telegram_update_offset"
TOKEN_KEY = "telegram_bot_token"


class TelegramRepository:
    """Keep Telegram state in the same local database as catalogue data."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def offset(self) -> int | None:
        from ..database.models import Setting

        setting = self.session.get(Setting, OFFSET_KEY)
        if setting is None or not setting.value:
            return None
        try:
            return int(setting.value)
        except (TypeError, ValueError):
            return None

    def set_offset(self, offset: int) -> None:
        from ..database.models import Setting

        setting = self.session.get(Setting, OFFSET_KEY)
        if setting is None:
            self.session.add(Setting(key=OFFSET_KEY, value=str(offset)))
        else:
            setting.value = str(offset)
            setting.updated_at = datetime.now()
        self.session.flush()

    def token(self) -> str | None:
        from ..database.models import Setting

        setting = self.session.get(Setting, TOKEN_KEY)
        return None if setting is None else setting.value

    def set_token(self, token: str) -> None:
        from ..database.models import Setting

        token = token.strip()
        if not token:
            raise ValueError("Введите токен Telegram.")
        setting = self.session.get(Setting, TOKEN_KEY)
        if setting is None:
            self.session.add(Setting(key=TOKEN_KEY, value=token))
        else:
            setting.value = token
            setting.updated_at = datetime.now()
        self.session.flush()

    def channels(self) -> list[TelegramChannel]:
        return list(self.session.scalars(select(TelegramChannel).order_by(TelegramChannel.id)))

    def channel(self, channel_id: str) -> TelegramChannel | None:
        return self.session.scalar(select(TelegramChannel).where(TelegramChannel.channel_id == str(channel_id)))

    def discovered_channels(self) -> list[TelegramChannel]:
        return list(
            self.session.scalars(
                select(TelegramChannel)
                .where(TelegramChannel.portfolio_id.is_(None))
                .order_by(TelegramChannel.id.desc())
            )
        )

    def record_discovered_channel(self, channel_id: str, title: str | None = None) -> TelegramChannel:
        existing = self.channel(channel_id)
        if existing is not None:
            if title and not existing.title:
                existing.title = title[:255]
            self.session.flush()
            return existing
        channel = TelegramChannel(
            portfolio_id=None,
            channel_id=str(channel_id),
            title=None if title is None else title[:255],
        )
        self.session.add(channel)
        self.session.flush()
        return channel

    def bind_channel(self, portfolio_id: int, channel_id: str, title: str | None = None) -> TelegramChannel:
        normalized = str(channel_id).strip()
        if not normalized:
            raise ValueError("Введите ID канала.")
        existing = self.channel(normalized)
        if existing is not None:
            existing.portfolio_id = portfolio_id
            if title:
                existing.title = title[:255]
            self.session.flush()
            return existing
        channel = TelegramChannel(
            portfolio_id=portfolio_id,
            channel_id=normalized,
            title=None if title is None else title[:255],
        )
        self.session.add(channel)
        self.session.flush()
        return channel

    def unbind_channel(self, channel_id: str) -> None:
        channel = self.channel(channel_id)
        if channel is not None:
            self.session.delete(channel)
            self.session.flush()

    def has_import(self, channel_id: str, message_id: int, update_id: int) -> bool:
        statement = select(TelegramImport.id).where(
            TelegramImport.status == "imported",
            (
                (TelegramImport.channel_id == str(channel_id))
                & (TelegramImport.message_id == message_id)
            )
            | (TelegramImport.update_id == update_id)
        )
        return self.session.scalar(statement) is not None

    def record_import(self, channel_id: str, message_id: int, update_id: int) -> TelegramImport:
        existing = self.session.scalar(select(TelegramImport).where(TelegramImport.update_id == update_id))
        if existing is not None:
            existing.channel_id = str(channel_id)
            existing.message_id = message_id
            existing.status = "imported"
            existing.error_message = None
            existing.processed_at = datetime.now()
            self.session.flush()
            return existing
        record = TelegramImport(
            channel_id=str(channel_id),
            message_id=message_id,
            update_id=update_id,
            status="imported",
            processed_at=datetime.now(),
        )
        self.session.add(record)
        self.session.flush()
        return record

    def commit_import(self, channel_id: str, message_id: int, update_id: int) -> TelegramImport | None:
        """Record an import, returning None when another update already won the race."""

        try:
            return self.record_import(channel_id, message_id, update_id)
        except IntegrityError:
            self.session.rollback()
            return None

    def record_diagnostic(
        self,
        update_id: int,
        status: str,
        message: str,
        channel_id: str | None = None,
        message_id: int | None = None,
    ) -> TelegramImport:
        record = self.session.scalar(select(TelegramImport).where(TelegramImport.update_id == update_id))
        if record is None:
            record = TelegramImport(
                update_id=update_id,
                channel_id=channel_id,
                message_id=message_id,
                status=status,
                error_message=message[:512],
                processed_at=datetime.now(),
            )
            self.session.add(record)
        else:
            record.status = status
            record.error_message = message[:512]
            record.processed_at = datetime.now()
        self.session.flush()
        return record

    def recent_diagnostics(self, limit: int = 20) -> list[TelegramImport]:
        statement = (
            select(TelegramImport)
            .where(TelegramImport.status != "imported")
            .order_by(TelegramImport.id.desc())
            .limit(limit)
        )
        return list(self.session.scalars(statement))

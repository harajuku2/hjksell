"""Persistence helpers for Telegram bindings, offsets, and imports."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..database.models import TelegramChannel, TelegramConfig, TelegramImport


OFFSET_KEY = "telegram_update_offset"
TOKEN_KEY = "telegram_bot_token"


class TelegramRepository:
    """Keep Telegram state in the same local database as catalogue data."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def config(self, portfolio_id: int) -> TelegramConfig:
        config = self.session.get(TelegramConfig, portfolio_id)
        if config is None:
            config = TelegramConfig(portfolio_id=portfolio_id)
            self.session.add(config)
            self.session.flush()
        return config

    def offset(self, portfolio_id: int = 1) -> int | None:
        value = self.config(portfolio_id).update_offset
        return None if value is None else int(value)

    def set_offset(self, portfolio_id: int, offset: int) -> None:
        self.config(portfolio_id).update_offset = offset
        self.session.flush()

    def token(self, portfolio_id: int = 1) -> str | None:
        return self.config(portfolio_id).token

    def set_token(self, portfolio_id: int | str, token: str | None = None) -> None:
        if token is None:
            token = str(portfolio_id)
            portfolio_id = 1
        token = token.strip()
        if not token:
            raise ValueError("Введите токен Telegram.")
        self.config(int(portfolio_id)).token = token
        self.session.flush()

    def channels(self) -> list[TelegramChannel]:
        return list(self.session.scalars(select(TelegramChannel).order_by(TelegramChannel.id)))

    def channel(self, channel_id: str, portfolio_id: int | None = None) -> TelegramChannel | None:
        statement = select(TelegramChannel).where(TelegramChannel.channel_id == str(channel_id))
        if portfolio_id is not None:
            exact = self.session.scalar(statement.where(TelegramChannel.portfolio_id == portfolio_id))
            if exact is not None:
                return exact
            return self.session.scalar(statement.where(TelegramChannel.portfolio_id.is_(None)))
        return self.session.scalar(statement)

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
        existing = self.channel(normalized, portfolio_id)
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

    def has_import(self, portfolio_id: int, channel_id: str, message_id: int, update_id: int) -> bool:
        statement = select(TelegramImport.id).where(
            TelegramImport.status == "imported",
            TelegramImport.portfolio_id == portfolio_id,
            (
                (TelegramImport.channel_id == str(channel_id))
                & (TelegramImport.message_id == message_id)
            )
            | (TelegramImport.update_id == update_id)
        )
        return self.session.scalar(statement) is not None

    def record_import(self, portfolio_id: int, channel_id: str, message_id: int, update_id: int) -> TelegramImport:
        existing = self.session.scalar(select(TelegramImport).where(
            TelegramImport.portfolio_id == portfolio_id,
            TelegramImport.update_id == update_id,
        ))
        if existing is not None:
            existing.channel_id = str(channel_id)
            existing.message_id = message_id
            existing.status = "imported"
            existing.error_message = None
            existing.processed_at = datetime.now()
            self.session.flush()
            return existing
        record = TelegramImport(
            portfolio_id=portfolio_id,
            channel_id=str(channel_id),
            message_id=message_id,
            update_id=update_id,
            status="imported",
            processed_at=datetime.now(),
        )
        self.session.add(record)
        self.session.flush()
        return record

    def commit_import(self, portfolio_id: int, channel_id: str, message_id: int, update_id: int) -> TelegramImport | None:
        """Record an import, returning None when another update already won the race."""

        try:
            return self.record_import(portfolio_id, channel_id, message_id, update_id)
        except IntegrityError:
            self.session.rollback()
            return None

    def record_diagnostic(
        self,
        update_id: int,
        status: str,
        message: str,
        portfolio_id: int | None = None,
        channel_id: str | None = None,
        message_id: int | None = None,
    ) -> TelegramImport:
        record = self.session.scalar(select(TelegramImport).where(
            TelegramImport.portfolio_id == portfolio_id,
            TelegramImport.update_id == update_id,
        ))
        if record is None:
            record = TelegramImport(
                update_id=update_id,
                portfolio_id=portfolio_id,
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

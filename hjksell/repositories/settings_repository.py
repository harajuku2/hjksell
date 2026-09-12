"""Persistence for application settings such as the current exchange rate."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from ..database.models import ExchangeRateHistory, Setting
from ..services.finance import rate

CURRENT_RATE_KEY = "exchange_rate"
DEFAULT_EXCHANGE_RATE = Decimal("0.8500")


class SettingsRepository:
    """Read and write settings while keeping exchange-rate changes auditable."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, key: str, default: str | None = None) -> str | None:
        setting = self.session.get(Setting, key)
        return default if setting is None else setting.value

    def set(self, key: str, value: str) -> Setting:
        setting = self.session.get(Setting, key)
        if setting is None:
            setting = Setting(key=key, value=value)
            self.session.add(setting)
        else:
            setting.value = value
            setting.updated_at = datetime.now()
        self.session.flush()
        return setting

    def current_exchange_rate(self) -> Decimal:
        value = self.get(CURRENT_RATE_KEY)
        if value is None:
            self.set(CURRENT_RATE_KEY, str(DEFAULT_EXCHANGE_RATE))
            return DEFAULT_EXCHANGE_RATE
        return rate(Decimal(value))

    def set_exchange_rate(self, value: Decimal) -> Decimal:
        if not value.is_finite() or value <= 0:
            raise ValueError("Курс должен быть больше нуля.")
        normalized = rate(value)
        self.set(CURRENT_RATE_KEY, str(normalized))
        self.session.add(ExchangeRateHistory(rate=normalized, effective_from=datetime.now()))
        self.session.flush()
        return normalized

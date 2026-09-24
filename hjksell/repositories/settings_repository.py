"""Persistence for application settings such as the current exchange rate."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database.models import ExchangeRateHistory, PortfolioCurrencySetting, Setting
from ..services.finance import money, rate

CURRENT_RATE_KEY = "exchange_rate"
DEFAULT_EXCHANGE_RATE = Decimal("0.8500")
DEFAULT_PURCHASE_CURRENCY = "PLN"
DEFAULT_SALE_CURRENCY = "BYN"

PURCHASE_CURRENCIES = ("PLN", "EUR", "USD", "CNY", "JPY", "SEK", "GBP", "CZK", "DKK", "NOK", "CHF", "TRY", "RUB", "BYN")
SALE_CURRENCIES = PURCHASE_CURRENCIES


@dataclass(frozen=True)
class PortfolioCurrencyProfile:
    purchase_currency: str
    sale_currency: str
    exchange_rate: Decimal
    automatic_expense_amount: Decimal
    automatic_expense_currency: str
    automatic_expense_purchase_rate: Decimal


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

    def current_exchange_rate(self, portfolio_id: int | None = None) -> Decimal:
        if portfolio_id is not None:
            return self.currency_profile(portfolio_id).exchange_rate
        value = self.get(CURRENT_RATE_KEY)
        if value is None:
            self.set(CURRENT_RATE_KEY, str(DEFAULT_EXCHANGE_RATE))
            return DEFAULT_EXCHANGE_RATE
        return rate(Decimal(value))

    def set_exchange_rate(self, value: Decimal, portfolio_id: int | None = None) -> Decimal:
        if not value.is_finite() or value <= 0:
            raise ValueError("Курс должен быть больше нуля.")
        normalized = rate(value)
        if portfolio_id is not None:
            profile = self._currency_row(portfolio_id)
            profile.exchange_rate = normalized
            profile.updated_at = datetime.now()
            self.session.flush()
            return normalized
        self.set(CURRENT_RATE_KEY, str(normalized))
        for profile in self.session.scalars(select(PortfolioCurrencySetting)):
            profile.exchange_rate = normalized
            profile.updated_at = datetime.now()
        self.session.add(ExchangeRateHistory(rate=normalized, effective_from=datetime.now()))
        self.session.flush()
        return normalized

    def currency_profile(self, portfolio_id: int) -> PortfolioCurrencyProfile:
        row = self._currency_row(portfolio_id)
        return PortfolioCurrencyProfile(
            purchase_currency=row.purchase_currency,
            sale_currency=row.sale_currency,
            exchange_rate=rate(row.exchange_rate),
            automatic_expense_amount=money(row.automatic_expense_amount),
            automatic_expense_currency=row.automatic_expense_currency,
            automatic_expense_purchase_rate=rate(row.automatic_expense_purchase_rate),
        )

    def set_automatic_expense(
        self,
        portfolio_id: int,
        amount: Decimal,
        currency: str,
        purchase_rate: Decimal,
    ) -> PortfolioCurrencyProfile:
        normalized_currency = currency.strip().upper()
        if normalized_currency not in PURCHASE_CURRENCIES:
            raise ValueError("Валюта автоматического расхода не поддерживается.")
        if not amount.is_finite() or amount < 0:
            raise ValueError("Автоматический расход не может быть отрицательным.")
        if not purchase_rate.is_finite() or purchase_rate <= 0:
            raise ValueError("Курс автоматического расхода должен быть больше нуля.")
        row = self._currency_row(portfolio_id)
        row.automatic_expense_amount = money(amount)
        row.automatic_expense_currency = normalized_currency
        row.automatic_expense_purchase_rate = rate(purchase_rate)
        row.updated_at = datetime.now()
        self.session.flush()
        return self.currency_profile(portfolio_id)

    def set_currency_profile(
        self,
        portfolio_id: int,
        purchase_currency: str,
        sale_currency: str,
        exchange_rate: Decimal,
    ) -> PortfolioCurrencyProfile:
        purchase = purchase_currency.strip().upper()
        sale = sale_currency.strip().upper()
        if purchase not in PURCHASE_CURRENCIES:
            raise ValueError("Эта валюта закупки не поддерживается.")
        if sale not in SALE_CURRENCIES:
            raise ValueError("Эта валюта продажи не поддерживается.")
        if not exchange_rate.is_finite() or exchange_rate <= 0:
            raise ValueError("Курс должен быть больше нуля.")
        row = self._currency_row(portfolio_id)
        if purchase != row.purchase_currency and row.automatic_expense_amount > 0:
            raise ValueError(
                "Сначала обновите автоматический расход: его курс привязан к текущей валюте закупки."
            )
        row.purchase_currency = purchase
        row.sale_currency = sale
        row.exchange_rate = rate(exchange_rate)
        row.updated_at = datetime.now()
        self.session.flush()
        return self.currency_profile(portfolio_id)

    def _currency_row(self, portfolio_id: int) -> PortfolioCurrencySetting:
        row = self.session.get(PortfolioCurrencySetting, portfolio_id)
        if row is None:
            row = PortfolioCurrencySetting(
                portfolio_id=portfolio_id,
                purchase_currency=DEFAULT_PURCHASE_CURRENCY,
                sale_currency=DEFAULT_SALE_CURRENCY,
                exchange_rate=self.current_exchange_rate(),
                automatic_expense_amount=Decimal("0.00"),
                automatic_expense_currency=DEFAULT_PURCHASE_CURRENCY,
                automatic_expense_purchase_rate=Decimal("1.0000"),
            )
            self.session.add(row)
            self.session.flush()
        return row

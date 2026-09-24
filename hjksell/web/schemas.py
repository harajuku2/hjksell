"""JSON contracts for the local Catalog API."""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ExchangeRateUpdate(StrictModel):
    rate: str
    portfolio_id: int | None = None


class CurrencySettingsUpdate(StrictModel):
    portfolio_id: int
    purchase_currency: str
    sale_currency: str
    rate: str


class AutomaticExpenseUpdate(StrictModel):
    portfolio_id: int
    amount: str
    expense_currency: str


class PortfolioRename(StrictModel):
    name: str


class PortfolioCreate(StrictModel):
    name: str


class TelegramConfigUpdate(StrictModel):
    portfolio_id: int
    token: str | None = None
    channel_id: str | None = None


class TelegramTokenCheck(StrictModel):
    token: str


class MonthlyValuesUpdate(StrictModel):
    portfolio_id: int
    year: int
    month: int
    expenses: str
    other_income: str
    advertising: str


class ItemCreate(StrictModel):
    portfolio_id: int
    purchase_price_pln: str
    purchase_date: date


class ItemUpdate(StrictModel):
    portfolio_id: int
    purchase_price_pln: str | None = None
    purchase_expense: str | None = None
    purchase_date: date | None = None
    exchange_rate: str | None = None


class SaleUpdate(StrictModel):
    portfolio_id: int
    sale_price_byn: str
    sale_date: date | None = None


class SaleDateUpdate(StrictModel):
    portfolio_id: int
    sale_date: date


CatalogFilter = Literal["all", "stock", "sold", "no_revenue"]

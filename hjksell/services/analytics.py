"""Portfolio and monthly analytics business logic."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from statistics import mean

from ..database.models import ItemStatus
from ..repositories.item_repository import ItemRepository
from .finance import calculate_profit, calculate_x


def _period_contains(value: date | None, year: int, month: int) -> bool:
    return value is not None and value.year == year and value.month == month


@dataclass(frozen=True)
class MonthlyMetrics:
    invested: Decimal
    purchased_count: int
    revenue: Decimal
    sold_count: int
    realized_profit: Decimal
    average_x: Decimal | None
    roi: Decimal | None
    expenses: Decimal
    net_profit: Decimal
    roi_after_expenses: Decimal | None


class AnalyticsService:
    def __init__(self, item_repository: ItemRepository) -> None:
        self.repository = item_repository

    def monthly_metrics(self, portfolio_id: int, year: int, month: int) -> MonthlyMetrics:
        items = self.repository.active_items(portfolio_id)
        purchased = [item for item in items if _period_contains(item.purchase_date, year, month)]
        sold = [item for item in items if _period_contains(item.sale_date, year, month) and item.sale_price_byn is not None]
        invested = sum((item.cost_byn for item in purchased), Decimal("0.00"))
        revenue = sum((item.sale_price_byn for item in sold), Decimal("0.00"))
        realized_profit = sum((calculate_profit(item.sale_price_byn, item.cost_byn) or Decimal("0.00") for item in sold), Decimal("0.00"))
        costs_of_sold = sum((item.cost_byn for item in sold), Decimal("0.00"))
        x_values = [calculate_x(item.sale_price_byn, item.cost_byn) for item in sold]
        x_values = [value for value in x_values if value is not None]
        average_x = None if not x_values else (sum(x_values, Decimal("0")) / Decimal(len(x_values))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        roi = None if costs_of_sold == 0 else (realized_profit / costs_of_sold * Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        expenses = self.repository.monthly_expense(portfolio_id, year, month)
        net_profit = realized_profit - expenses
        roi_after_expenses = None if costs_of_sold == 0 else (net_profit / costs_of_sold * Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        return MonthlyMetrics(invested, len(purchased), revenue, len(sold), realized_profit, average_x, roi, expenses, net_profit, roi_after_expenses)

    def warehouse_value(self, portfolio_id: int) -> Decimal:
        return sum(
            (item.cost_byn for item in self.repository.active_items(portfolio_id) if item.status == ItemStatus.IN_STOCK.value),
            Decimal("0.00"),
        )

    def average_sale_days(self, portfolio_id: int) -> Decimal | None:
        items = self.repository.active_items(portfolio_id)
        days = [(item.sale_date - item.purchase_date).days for item in items if item.sale_date is not None]
        return None if not days else Decimal(str(mean(days))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

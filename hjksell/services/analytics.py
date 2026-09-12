"""Portfolio analytics.

The catalogue deliberately groups rows by purchase month, while analytics
groups purchases and sales by their own dates.  Keeping the date filtering in
this service prevents the UI from accidentally mixing the two timelines.
"""

from __future__ import annotations

from calendar import monthrange
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from enum import StrEnum
from typing import Iterable

from ..database.models import ItemStatus
from ..repositories.item_repository import ItemRepository
from .finance import calculate_x

CENT = Decimal("0.01")


class PeriodPreset(StrEnum):
    CURRENT_MONTH = "current_month"
    PREVIOUS_MONTH = "previous_month"
    THREE_MONTHS = "3_months"
    SIX_MONTHS = "6_months"
    CURRENT_YEAR = "current_year"
    ALL_TIME = "all_time"
    CURRENT = "current_month"
    LAST_MONTH = "previous_month"
    LAST_3_MONTHS = "3_months"
    LAST_6_MONTHS = "6_months"


@dataclass(frozen=True)
class AnalyticsPeriod:
    """An inclusive calendar period used by the detailed analytics screen."""

    start_date: date
    end_date: date

    def __post_init__(self) -> None:
        if self.start_date > self.end_date:
            raise ValueError("Дата начала периода не может быть позже даты окончания.")

    @classmethod
    def custom(cls, start_date: date, end_date: date) -> "AnalyticsPeriod":
        return cls(start_date, end_date)

    @property
    def start(self) -> date:
        return self.start_date

    @property
    def end(self) -> date:
        return self.end_date


# Short compatibility name for integrations that call the object simply
# ``Period``.
Period = AnalyticsPeriod
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


@dataclass(frozen=True)
class AnalyticsMetrics:
    """All values shown by the detailed analytics screen."""

    invested: Decimal
    purchased_count: int
    revenue: Decimal
    sold_count: int
    realized_profit: Decimal
    expenses: Decimal
    net_profit: Decimal
    average_x: Decimal | None
    roi: Decimal | None
    roi_after_expenses: Decimal | None
    average_cost: Decimal | None
    average_sale: Decimal | None
    average_profit: Decimal | None
    best_x: Decimal | None
    worst_x: Decimal | None
    average_sale_days: Decimal | None
    in_stock_count: int
    warehouse_value: Decimal

    # Friendly aliases make the service convenient for callers without
    # changing the stable, explicit field names above.
    @property
    def profit(self) -> Decimal:
        return self.realized_profit

    @property
    def purchased(self) -> int:
        return self.purchased_count

    @property
    def sold(self) -> int:
        return self.sold_count

    @property
    def avg_x(self) -> Decimal | None:
        return self.average_x

    @property
    def avg_cost(self) -> Decimal | None:
        return self.average_cost

    @property
    def avg_sale(self) -> Decimal | None:
        return self.average_sale

    @property
    def avg_profit(self) -> Decimal | None:
        return self.average_profit

    @property
    def avg_sale_days(self) -> Decimal | None:
        return self.average_sale_days

    @property
    def stock_count(self) -> int:
        return self.in_stock_count

    @property
    def average_cost_for_purchases(self) -> Decimal | None:
        return self.average_cost

    @property
    def average_sale_for_sales(self) -> Decimal | None:
        return self.average_sale

    @property
    def average_profit_per_sold_item(self) -> Decimal | None:
        return self.average_profit


@dataclass(frozen=True)
class MonthlyAnalytics:
    year: int
    month: int
    invested: Decimal
    purchased_count: int
    revenue: Decimal
    sold_count: int
    realized_profit: Decimal
    expenses: Decimal
    net_profit: Decimal

    @property
    def label(self) -> str:
        return f"{self.year:04d}-{self.month:02d}"


@dataclass(frozen=True)
class AnalyticsReport:
    period: AnalyticsPeriod
    metrics: AnalyticsMetrics
    monthly: tuple[MonthlyAnalytics, ...]


def _money(value: Decimal) -> Decimal:
    if not value.is_finite():
        return Decimal("0.00")
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def _finite(value: Decimal | None) -> Decimal:
    """Normalise malformed legacy numeric values before doing arithmetic."""
    if value is None or not value.is_finite():
        return Decimal("0.00")
    return value


def _item_profit(item) -> Decimal:
    return _money(_finite(item.sale_price_byn) - _finite(item.cost_byn))


def _item_x(item) -> Decimal | None:
    sale = _finite(item.sale_price_byn)
    cost = _finite(item.cost_byn)
    if item.sale_price_byn is None or cost == 0:
        return None
    try:
        return calculate_x(sale, cost)
    except (ArithmeticError, ValueError):
        return None


def _average(values: Iterable[Decimal | int]) -> Decimal | None:
    values = list(values)
    if not values:
        return None
    return _money(sum((Decimal(str(value)) for value in values), Decimal("0")) / Decimal(len(values)))


def _month_start(year: int, month: int) -> date:
    return date(year, month, 1)


def _add_months(value: date, count: int) -> date:
    index = value.year * 12 + value.month - 1 + count
    return date(index // 12, index % 12 + 1, 1)


def _month_end(value: date) -> date:
    return date(value.year, value.month, monthrange(value.year, value.month)[1])


def _period_contains(value: date | None, period: AnalyticsPeriod) -> bool:
    return value is not None and period.start_date <= value <= period.end_date


class AnalyticsService:
    def __init__(self, item_repository: ItemRepository) -> None:
        self.repository = item_repository

    def resolve_period(
        self,
        preset: PeriodPreset | str = PeriodPreset.CURRENT_MONTH,
        *,
        portfolio_id: int | None = None,
        reference_date: date | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> AnalyticsPeriod:
        """Resolve a preset or explicit custom dates into an inclusive period."""

        if start_date is not None or end_date is not None:
            if start_date is None or end_date is None:
                raise ValueError("Для произвольного периода нужны обе даты.")
            return AnalyticsPeriod(start_date, end_date)
        if isinstance(preset, AnalyticsPeriod):
            return preset
        today = reference_date or date.today()
        try:
            preset = PeriodPreset(preset)
        except ValueError:
            aliases = {
                "current": PeriodPreset.CURRENT_MONTH,
                "month": PeriodPreset.CURRENT_MONTH,
                "текущий месяц": PeriodPreset.CURRENT_MONTH,
                "previous": PeriodPreset.PREVIOUS_MONTH,
                "предыдущий месяц": PeriodPreset.PREVIOUS_MONTH,
                "3": PeriodPreset.THREE_MONTHS,
                "3 месяца": PeriodPreset.THREE_MONTHS,
                "6": PeriodPreset.SIX_MONTHS,
                "6 месяцев": PeriodPreset.SIX_MONTHS,
                "year": PeriodPreset.CURRENT_YEAR,
                "текущий год": PeriodPreset.CURRENT_YEAR,
                "all": PeriodPreset.ALL_TIME,
                "всё время": PeriodPreset.ALL_TIME,
                "все время": PeriodPreset.ALL_TIME,
            }
            preset = aliases.get(str(preset).lower(), PeriodPreset.CURRENT_MONTH)
        current = _month_start(today.year, today.month)
        if preset == PeriodPreset.CURRENT_MONTH:
            return AnalyticsPeriod(current, _month_end(current))
        if preset == PeriodPreset.PREVIOUS_MONTH:
            previous = _add_months(current, -1)
            return AnalyticsPeriod(previous, _month_end(previous))
        if preset in (PeriodPreset.THREE_MONTHS, PeriodPreset.SIX_MONTHS):
            months = 3 if preset == PeriodPreset.THREE_MONTHS else 6
            start = _add_months(current, -(months - 1))
            return AnalyticsPeriod(start, _month_end(current))
        if preset == PeriodPreset.CURRENT_YEAR:
            return AnalyticsPeriod(date(today.year, 1, 1), date(today.year, 12, 31))

        # "All time" is based on actual records, rather than date.min/date.max,
        # so an empty database remains a useful current-month view.
        items = self.repository.active_items_for_analytics(portfolio_id)
        dates = [value for item in items for value in (item.purchase_date, item.sale_date) if value is not None]
        for year, month, _amount in self.repository.all_monthly_expenses(portfolio_id):
            dates.append(_month_start(year, month))
        return AnalyticsPeriod(min(dates), max(dates)) if dates else AnalyticsPeriod(current, _month_end(current))

    def monthly_metrics(self, portfolio_id: int, year: int, month: int) -> MonthlyMetrics:
        period = AnalyticsPeriod(_month_start(year, month), _month_end(_month_start(year, month)))
        return self._metrics_for_period(portfolio_id, period)

    def _metrics_for_period(self, portfolio_id: int, period: AnalyticsPeriod) -> MonthlyMetrics:
        items = self.repository.active_items(portfolio_id)
        purchased = [item for item in items if _period_contains(item.purchase_date, period)]
        sold = [item for item in items if _period_contains(item.sale_date, period) and item.sale_price_byn is not None]
        invested = _money(sum((_finite(item.cost_byn) for item in purchased), Decimal("0")))
        revenue = _money(sum((_finite(item.sale_price_byn) for item in sold), Decimal("0")))
        realized_profit = _money(sum((_item_profit(item) for item in sold), Decimal("0")))
        costs_of_sold = sum((_finite(item.cost_byn) for item in sold), Decimal("0"))
        x_values = [value for value in (_item_x(item) for item in sold) if value is not None]
        average_x = _average(x_values)
        roi = None if costs_of_sold == 0 else _money(realized_profit / costs_of_sold * Decimal("100"))
        expenses = _money(self.repository.monthly_expense(portfolio_id, period.start_date.year, period.start_date.month))
        net_profit = _money(realized_profit - expenses)
        roi_after_expenses = None if costs_of_sold == 0 else _money(net_profit / costs_of_sold * Decimal("100"))
        return MonthlyMetrics(invested, len(purchased), revenue, len(sold), realized_profit, average_x, roi, expenses, net_profit, roi_after_expenses)

    def detailed_metrics(
        self,
        portfolio_id: int,
        period: AnalyticsPeriod | PeriodPreset | str | tuple[date, date] | None = None,
        *,
        reference_date: date | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> AnalyticsMetrics:
        resolved = self._coerce_period(period, reference_date, start_date, end_date, portfolio_id)
        items = self.repository.active_items(portfolio_id)
        purchased = [item for item in items if _period_contains(item.purchase_date, resolved)]
        sold = [item for item in items if _period_contains(item.sale_date, resolved) and item.sale_price_byn is not None]
        invested = _money(sum((_finite(item.cost_byn) for item in purchased), Decimal("0")))
        revenue = _money(sum((_finite(item.sale_price_byn) for item in sold), Decimal("0")))
        profits = [_item_profit(item) for item in sold]
        realized_profit = _money(sum(profits, Decimal("0")))
        sold_cost = sum((_finite(item.cost_byn) for item in sold), Decimal("0"))
        x_values = [value for value in (_item_x(item) for item in sold) if value is not None]
        expenses = _money(sum((_finite(amount) for _year, _month, amount in self.repository.monthly_expenses_between(portfolio_id, resolved.start_date, resolved.end_date)), Decimal("0")))
        net_profit = _money(realized_profit - expenses)
        in_stock = [item for item in items if item.status == ItemStatus.IN_STOCK.value]
        return AnalyticsMetrics(
            invested=invested,
            purchased_count=len(purchased),
            revenue=revenue,
            sold_count=len(sold),
            realized_profit=realized_profit,
            expenses=expenses,
            net_profit=net_profit,
            average_x=_average(x_values),
            roi=None if sold_cost == 0 else _money(realized_profit / sold_cost * Decimal("100")),
            roi_after_expenses=None if sold_cost == 0 else _money(net_profit / sold_cost * Decimal("100")),
            average_cost=None if not purchased else _money(invested / Decimal(len(purchased))),
            average_sale=None if not sold else _money(revenue / Decimal(len(sold))),
            average_profit=_average(profits),
            best_x=max(x_values) if x_values else None,
            worst_x=min(x_values) if x_values else None,
            average_sale_days=_average(
                (item.sale_date - item.purchase_date).days
                for item in sold
                if item.sale_date is not None and item.purchase_date is not None
            ),
            in_stock_count=len(in_stock),
            warehouse_value=_money(sum((_finite(item.cost_byn) for item in in_stock), Decimal("0"))),
        )

    def _coerce_period(self, period, reference_date, start_date, end_date, portfolio_id: int | None = None) -> AnalyticsPeriod:
        if isinstance(period, tuple):
            period = AnalyticsPeriod(*period)
        if period is None:
            period = PeriodPreset.CURRENT_MONTH
        return self.resolve_period(period, portfolio_id=portfolio_id, reference_date=reference_date, start_date=start_date, end_date=end_date)

    # Public aliases used by integrations and older callers.
    period_metrics = detailed_metrics
    metrics = detailed_metrics
    calculate_metrics = detailed_metrics

    def monthly_breakdown(
        self,
        portfolio_id: int,
        period: AnalyticsPeriod | PeriodPreset | str | tuple[date, date] | None = None,
        *,
        reference_date: date | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[MonthlyAnalytics]:
        resolved = self._coerce_period(period, reference_date, start_date, end_date, portfolio_id)
        month = _month_start(resolved.start_date.year, resolved.start_date.month)
        result: list[MonthlyAnalytics] = []
        while month <= resolved.end_date:
            month_period = AnalyticsPeriod(
                max(resolved.start_date, month),
                min(resolved.end_date, _month_end(month)),
            )
            metrics = self._metrics_for_period(portfolio_id, month_period)
            result.append(MonthlyAnalytics(
                month.year, month.month, metrics.invested, metrics.purchased_count,
                metrics.revenue, metrics.sold_count, metrics.realized_profit,
                metrics.expenses, metrics.net_profit,
            ))
            month = _add_months(month, 1)
        return result

    def report(self, portfolio_id: int, period=None, **kwargs) -> AnalyticsReport:
        resolved = self._coerce_period(
            period, kwargs.pop("reference_date", None), kwargs.pop("start_date", None), kwargs.pop("end_date", None), portfolio_id
        )
        return AnalyticsReport(resolved, self.detailed_metrics(portfolio_id, resolved), tuple(self.monthly_breakdown(portfolio_id, resolved)))

    def warehouse_value(self, portfolio_id: int) -> Decimal:
        return self.detailed_metrics(portfolio_id, AnalyticsPeriod(date.min, date.max)).warehouse_value

    def average_sale_days(self, portfolio_id: int) -> Decimal | None:
        return self.detailed_metrics(portfolio_id, AnalyticsPeriod(date.min, date.max)).average_sale_days

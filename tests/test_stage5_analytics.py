"""Stage-five detailed analytics coverage."""

from datetime import date
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from hjksell.database.models import Base, Item, ItemStatus
from hjksell.repositories.item_repository import ItemRepository
from hjksell.repositories.portfolio_repository import PortfolioRepository
from hjksell.services.analytics import AnalyticsPeriod, AnalyticsService, PeriodPreset


def make_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)


def item(session, portfolio_id, purchase, *, cost="85.00", sale=None, sold=None):
    return ItemRepository(session).add_item(Item(
        portfolio_id=portfolio_id,
        purchase_date=purchase,
        purchase_price_pln=Decimal(cost),
        exchange_rate=Decimal("1.0000"),
        cost_byn=Decimal(cost),
        status=ItemStatus.SOLD.value if sale is not None else ItemStatus.IN_STOCK.value,
        sale_price_byn=None if sale is None else Decimal(sale),
        sale_date=sold,
    ))


def test_arbitrary_period_keeps_purchase_and_sale_months_separate():
    with make_session() as session:
        mine, _ = PortfolioRepository(session).ensure_default_portfolios()
        item(session, mine.id, date(2026, 1, 30), sale="200.00", sold=date(2026, 2, 2))
        report = AnalyticsService(ItemRepository(session)).report(
            mine.id, AnalyticsPeriod(date(2026, 1, 1), date(2026, 2, 28))
        )
        assert report.metrics.invested == Decimal("85.00")
        assert report.metrics.revenue == Decimal("200.00")
        assert [month.invested for month in report.monthly] == [Decimal("85.00"), Decimal("0.00")]
        assert [month.revenue for month in report.monthly] == [Decimal("0.00"), Decimal("200.00")]


def test_period_presets_have_expected_calendar_ranges():
    with make_session() as session:
        service = AnalyticsService(ItemRepository(session))
        reference = date(2026, 9, 12)
        assert service.resolve_period(PeriodPreset.CURRENT_MONTH, reference_date=reference).start_date == date(2026, 9, 1)
        assert service.resolve_period(PeriodPreset.PREVIOUS_MONTH, reference_date=reference).start_date == date(2026, 8, 1)
        assert service.resolve_period(PeriodPreset.THREE_MONTHS, reference_date=reference).start_date == date(2026, 7, 1)
        assert service.resolve_period(PeriodPreset.SIX_MONTHS, reference_date=reference).start_date == date(2026, 4, 1)
        assert service.resolve_period(PeriodPreset.CURRENT_YEAR, reference_date=reference).start_date == date(2026, 1, 1)


def test_expenses_sum_across_months_and_profit_formulas():
    with make_session() as session:
        mine, _ = PortfolioRepository(session).ensure_default_portfolios()
        item(session, mine.id, date(2026, 1, 2), sale="200.00", sold=date(2026, 1, 8))
        item(session, mine.id, date(2026, 2, 2), sale="300.00", sold=date(2026, 2, 8))
        repo = ItemRepository(session)
        repo.set_monthly_expense(mine.id, 2026, 1, Decimal("10"))
        repo.set_monthly_expense(mine.id, 2026, 2, Decimal("20"))
        metrics = AnalyticsService(repo).detailed_metrics(
            mine.id, start_date=date(2026, 1, 1), end_date=date(2026, 2, 28)
        )
        assert metrics.expenses == Decimal("30.00")
        assert metrics.realized_profit == Decimal("330.00")
        assert metrics.net_profit == Decimal("300.00")
        assert metrics.roi == Decimal("194.12")
        assert metrics.roi_after_expenses == Decimal("176.47")


def test_averages_best_worst_days_and_warehouse():
    with make_session() as session:
        mine, _ = PortfolioRepository(session).ensure_default_portfolios()
        item(session, mine.id, date(2026, 1, 1), sale="170", sold=date(2026, 1, 11))
        item(session, mine.id, date(2026, 1, 1), sale="340", sold=date(2026, 1, 21), cost="100")
        item(session, mine.id, date(2026, 1, 5), cost="42")
        metrics = AnalyticsService(ItemRepository(session)).detailed_metrics(
            mine.id, AnalyticsPeriod(date(2026, 1, 1), date(2026, 1, 31))
        )
        assert metrics.average_sale_days == Decimal("15.00")
        assert metrics.best_x == Decimal("3.40")
        assert metrics.worst_x == Decimal("2.00")
        assert metrics.average_cost == Decimal("75.67")
        assert metrics.average_sale == Decimal("255.00")
        assert metrics.average_profit == Decimal("162.50")
        assert metrics.in_stock_count == 1
        assert metrics.warehouse_value == Decimal("42.00")


def test_soft_delete_portfolio_scope_and_empty_data():
    with make_session() as session:
        mine, friend = PortfolioRepository(session).ensure_default_portfolios()
        deleted = item(session, mine.id, date(2026, 1, 1), sale="500", sold=date(2026, 1, 2))
        ItemRepository(session).soft_delete(deleted)
        item(session, friend.id, date(2026, 1, 1), sale="100", sold=date(2026, 1, 2))
        service = AnalyticsService(ItemRepository(session))
        empty = service.detailed_metrics(mine.id, AnalyticsPeriod(date(2026, 1, 1), date(2026, 1, 31)))
        assert empty.revenue == Decimal("0.00")
        assert empty.average_x is None
        assert empty.roi is None
        assert service.detailed_metrics(friend.id, PeriodPreset.ALL_TIME).revenue == Decimal("100.00")

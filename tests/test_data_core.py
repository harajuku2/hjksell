"""Stage-two tests for persistence, finance, and analytics."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session

from hjksell.database.models import Base, Item, ItemStatus
from hjksell.repositories.item_repository import ItemRepository
from hjksell.repositories.portfolio_repository import PortfolioRepository
from hjksell.services.analytics import AnalyticsService
from hjksell.services.finance import (
    calculate_cost,
    calculate_profit,
    calculate_roi,
    calculate_x,
    item_metrics,
)


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture
def portfolios(session: Session):
    my_portfolio, friend_portfolio = PortfolioRepository(session).ensure_default_portfolios()
    session.commit()
    return my_portfolio, friend_portfolio


def add_item(
    session: Session,
    portfolio_id: int,
    *,
    purchase_date: date = date(2026, 8, 25),
    price: str = "100.00",
    rate: str = "0.8500",
    sale_price: str | None = None,
    sale_date: date | None = None,
) -> Item:
    item = Item(
        portfolio_id=portfolio_id,
        purchase_date=purchase_date,
        purchase_price_pln=Decimal(price),
        exchange_rate=Decimal(rate),
        cost_byn=calculate_cost(Decimal(price), Decimal(rate)),
        status=ItemStatus.SOLD.value if sale_price is not None else ItemStatus.IN_STOCK.value,
        sale_price_byn=None if sale_price is None else Decimal(sale_price),
        sale_date=sale_date,
    )
    return ItemRepository(session).add_item(item)


def test_database_contains_required_tables_and_two_portfolios(session: Session, portfolios) -> None:
    names = set(inspect(session.bind).get_table_names())
    assert {"portfolios", "items", "monthly_expenses", "settings", "exchange_rate_history", "telegram_channels", "telegram_imports"} <= names
    assert {portfolio.name for portfolio in portfolios} == {"МОЯ", "ДРУГА"}


def test_cost_profit_x_and_roi() -> None:
    cost = calculate_cost(Decimal("150"), Decimal("0.8500"))
    assert cost == Decimal("127.50")
    assert calculate_profit(Decimal("300"), cost) == Decimal("172.50")
    assert calculate_x(Decimal("300"), cost) == Decimal("2.35")
    assert calculate_roi(Decimal("300"), cost) == Decimal("135.29")


def test_roi_multiples() -> None:
    assert calculate_roi(Decimal("100"), Decimal("100")) == Decimal("0.00")
    assert calculate_roi(Decimal("200"), Decimal("100")) == Decimal("100.00")


def test_unprofitable_sale() -> None:
    assert calculate_profit(Decimal("80"), Decimal("100")) == Decimal("-20.00")
    assert calculate_roi(Decimal("80"), Decimal("100")) == Decimal("-20.00")


def test_unsold_item_metrics_are_none() -> None:
    assert item_metrics(None, Decimal("100")) == item_metrics(None, Decimal("100"))
    metrics = item_metrics(None, Decimal("100"))
    assert metrics.profit is None
    assert metrics.x is None
    assert metrics.roi is None


def test_month_of_purchase_is_separate_from_month_of_sale(session: Session, portfolios) -> None:
    my_portfolio, _ = portfolios
    add_item(session, my_portfolio.id, sale_price="250", sale_date=date(2026, 9, 10))
    repository = ItemRepository(session)
    august = AnalyticsService(repository).monthly_metrics(my_portfolio.id, 2026, 8)
    september = AnalyticsService(repository).monthly_metrics(my_portfolio.id, 2026, 9)
    assert august.invested == Decimal("85.00")
    assert august.purchased_count == 1
    assert august.revenue == Decimal("0.00")
    assert september.revenue == Decimal("250.00")
    assert september.sold_count == 1
    assert september.realized_profit == Decimal("165.00")


def test_monthly_expenses_and_net_profit(session: Session, portfolios) -> None:
    my_portfolio, _ = portfolios
    add_item(session, my_portfolio.id, sale_price="250", sale_date=date(2026, 9, 10))
    repository = ItemRepository(session)
    repository.set_monthly_expense(my_portfolio.id, 2026, 9, Decimal("20.00"))
    metrics = AnalyticsService(repository).monthly_metrics(my_portfolio.id, 2026, 9)
    assert metrics.expenses == Decimal("20.00")
    assert metrics.net_profit == Decimal("145.00")
    assert metrics.roi_after_expenses == Decimal("170.59")


def test_portfolios_are_independent(session: Session, portfolios) -> None:
    my_portfolio, friend_portfolio = portfolios
    add_item(session, my_portfolio.id, price="100", sale_price="200", sale_date=date(2026, 9, 1))
    add_item(session, friend_portfolio.id, price="50")
    repository = ItemRepository(session)
    analytics = AnalyticsService(repository)
    assert analytics.warehouse_value(my_portfolio.id) == Decimal("0.00")
    assert analytics.warehouse_value(friend_portfolio.id) == Decimal("42.50")
    assert analytics.monthly_metrics(friend_portfolio.id, 2026, 9).revenue == Decimal("0.00")


def test_soft_deleted_item_is_excluded_from_all_statistics(session: Session, portfolios) -> None:
    my_portfolio, _ = portfolios
    item = add_item(session, my_portfolio.id, sale_price="200", sale_date=date(2026, 9, 1))
    repository = ItemRepository(session)
    repository.soft_delete(item)
    metrics = AnalyticsService(repository).monthly_metrics(my_portfolio.id, 2026, 9)
    assert metrics.sold_count == 0
    assert metrics.revenue == Decimal("0.00")
    assert AnalyticsService(repository).warehouse_value(my_portfolio.id) == Decimal("0.00")


def test_warehouse_value_excludes_sold_items(session: Session, portfolios) -> None:
    my_portfolio, _ = portfolios
    add_item(session, my_portfolio.id, price="100")
    add_item(session, my_portfolio.id, price="200", sale_price="300", sale_date=date(2026, 9, 1))
    assert AnalyticsService(ItemRepository(session)).warehouse_value(my_portfolio.id) == Decimal("85.00")


def test_average_sale_time(session: Session, portfolios) -> None:
    my_portfolio, _ = portfolios
    add_item(session, my_portfolio.id, purchase_date=date(2026, 8, 1), sale_price="200", sale_date=date(2026, 8, 11))
    add_item(session, my_portfolio.id, purchase_date=date(2026, 8, 5), sale_price="200", sale_date=date(2026, 8, 25))
    assert AnalyticsService(ItemRepository(session)).average_sale_days(my_portfolio.id) == Decimal("15.00")

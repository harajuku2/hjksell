"""Item and monthly expense persistence operations."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database.models import Item, ItemStatus, MonthlyExpense


class ItemRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add_item(self, item: Item) -> Item:
        self.session.add(item)
        self.session.flush()
        return item

    def active_items(self, portfolio_id: int, status: str | None = None) -> list[Item]:
        conditions = [Item.portfolio_id == portfolio_id, Item.deleted_at.is_(None)]
        if status is not None:
            conditions.append(Item.status == status)
        statement = select(Item).where(*conditions).order_by(
            Item.purchase_date.desc(), Item.created_at.desc(), Item.id.desc()
        )
        return list(self.session.scalars(statement))

    def active_items_for_analytics(self, portfolio_id: int | None) -> list[Item]:
        """Return non-deleted items, optionally scoped to one portfolio.

        The optional scope is useful for resolving an all-time period without
        making the analytics service know anything about SQLAlchemy.
        """
        conditions = [Item.deleted_at.is_(None)]
        if portfolio_id is not None:
            conditions.append(Item.portfolio_id == portfolio_id)
        return list(self.session.scalars(select(Item).where(*conditions)))

    def get(self, item_id: int, portfolio_id: int | None = None) -> Item | None:
        item = self.session.get(Item, item_id)
        if item is None or item.deleted_at is not None:
            return None
        if portfolio_id is not None and item.portfolio_id != portfolio_id:
            return None
        return item

    def set_monthly_expense(self, portfolio_id: int, year: int, month: int, amount_byn: Decimal) -> MonthlyExpense:
        statement = select(MonthlyExpense).where(
            MonthlyExpense.portfolio_id == portfolio_id,
            MonthlyExpense.year == year,
            MonthlyExpense.month == month,
        )
        expense = self.session.scalar(statement)
        if expense is None:
            expense = MonthlyExpense(portfolio_id=portfolio_id, year=year, month=month, amount_byn=amount_byn)
            self.session.add(expense)
        else:
            expense.amount_byn = amount_byn
        self.session.flush()
        return expense

    def monthly_expense(self, portfolio_id: int, year: int, month: int) -> Decimal:
        statement = select(MonthlyExpense.amount_byn).where(
            MonthlyExpense.portfolio_id == portfolio_id,
            MonthlyExpense.year == year,
            MonthlyExpense.month == month,
        )
        return self.session.scalar(statement) or Decimal("0.00")

    def monthly_expenses_between(self, portfolio_id: int, start_date: date, end_date: date) -> list[tuple[int, int, Decimal]]:
        """Return expense rows whose calendar month overlaps an inclusive period."""
        statement = select(MonthlyExpense.year, MonthlyExpense.month, MonthlyExpense.amount_byn).where(
            MonthlyExpense.portfolio_id == portfolio_id,
        )
        result = []
        for year, month, amount in self.session.execute(statement):
            month_start = date(year, month, 1)
            # A monthly expense belongs to the month, even when a custom
            # period starts/ends in the middle of that month.
            if date(start_date.year, start_date.month, 1) <= month_start <= date(end_date.year, end_date.month, 1):
                result.append((year, month, amount))
        return result

    def all_monthly_expenses(self, portfolio_id: int | None) -> list[tuple[int, int, Decimal]]:
        conditions = [] if portfolio_id is None else [MonthlyExpense.portfolio_id == portfolio_id]
        return list(self.session.execute(select(MonthlyExpense.year, MonthlyExpense.month, MonthlyExpense.amount_byn).where(*conditions)))

    def soft_delete(self, item: Item) -> None:
        item.deleted_at = datetime.now()
        item.updated_at = item.deleted_at
        self.session.flush()

    def replace_photo(self, item: Item, photo_path: str) -> Item:
        item.photo_path = photo_path
        item.updated_at = datetime.now()
        self.session.flush()
        return item

    def sale(self, item: Item, sale_price_byn: Decimal, sale_date: date) -> Item:
        item.sale_price_byn = sale_price_byn
        item.sale_date = sale_date
        item.status = ItemStatus.SOLD.value
        item.updated_at = datetime.now()
        self.session.flush()
        return item

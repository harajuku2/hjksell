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

    def active_items(self, portfolio_id: int) -> list[Item]:
        statement = (
            select(Item)
            .where(Item.portfolio_id == portfolio_id, Item.deleted_at.is_(None))
            .order_by(Item.purchase_date.desc(), Item.created_at.desc(), Item.id.desc())
        )
        return list(self.session.scalars(statement))

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

    def soft_delete(self, item: Item) -> None:
        item.deleted_at = datetime.now()
        item.updated_at = item.deleted_at
        self.session.flush()

    def sale(self, item: Item, sale_price_byn: Decimal, sale_date: date) -> Item:
        item.sale_price_byn = sale_price_byn
        item.sale_date = sale_date
        item.status = ItemStatus.SOLD.value
        item.updated_at = datetime.now()
        self.session.flush()
        return item

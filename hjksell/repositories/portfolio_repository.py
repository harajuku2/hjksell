"""Portfolio persistence operations."""

from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..database.models import Item, MonthlyExpense, Portfolio, TelegramChannel, TelegramConfig, TelegramImport


class PortfolioRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def ensure_default_portfolios(self) -> tuple[Portfolio, Portfolio]:
        existing = {
            portfolio.id: portfolio
            for portfolio in self.session.scalars(select(Portfolio).order_by(Portfolio.id)).all()
        }
        for portfolio_id, name in ((1, "МОЯ"), (2, "ДРУГА")):
            if portfolio_id not in existing:
                existing[portfolio_id] = Portfolio(id=portfolio_id, name=name)
                self.session.add(existing[portfolio_id])
        self.session.flush()
        return existing[1], existing[2]

    def get(self, portfolio_id: int) -> Portfolio | None:
        return self.session.get(Portfolio, portfolio_id)

    def list_all(self) -> list[Portfolio]:
        return list(self.session.scalars(select(Portfolio).order_by(Portfolio.id)))

    def create(self, display_name: str) -> Portfolio:
        portfolio = Portfolio(name=display_name)
        self.session.add(portfolio)
        self.session.flush()
        return portfolio

    def rename(self, portfolio: Portfolio, display_name: str) -> Portfolio:
        portfolio.name = display_name
        self.session.flush()
        return portfolio

    def delete(self, portfolio: Portfolio) -> None:
        """Delete a portfolio and its portfolio-scoped records."""

        for model in (TelegramImport, TelegramChannel, TelegramConfig, MonthlyExpense, Item):
            self.session.execute(delete(model).where(model.portfolio_id == portfolio.id))
        self.session.delete(portfolio)
        self.session.flush()

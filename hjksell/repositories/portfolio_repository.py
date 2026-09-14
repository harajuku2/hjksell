"""Portfolio persistence operations."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database.models import Portfolio


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

    def rename(self, portfolio: Portfolio, display_name: str) -> Portfolio:
        portfolio.name = display_name
        self.session.flush()
        return portfolio

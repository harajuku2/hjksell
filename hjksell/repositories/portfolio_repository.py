"""Portfolio persistence operations."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database.models import Portfolio


class PortfolioRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def ensure_default_portfolios(self) -> tuple[Portfolio, Portfolio]:
        existing = {portfolio.name: portfolio for portfolio in self.session.scalars(select(Portfolio)).all()}
        for name in ("МОЯ", "ДРУГА"):
            if name not in existing:
                existing[name] = Portfolio(name=name)
                self.session.add(existing[name])
        self.session.flush()
        return existing["МОЯ"], existing["ДРУГА"]

    def get(self, portfolio_id: int) -> Portfolio | None:
        return self.session.get(Portfolio, portfolio_id)

    def list_all(self) -> list[Portfolio]:
        return list(self.session.scalars(select(Portfolio).order_by(Portfolio.id)))

"""Portfolio persistence operations."""

from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..database.models import (
    Item,
    MonthlyExpense,
    Portfolio,
    PortfolioCurrencySetting,
    TelegramChannel,
    TelegramConfig,
    TelegramImport,
)


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

    def list_for_owner(self, owner_telegram_id: int) -> list[Portfolio]:
        return list(self.session.scalars(
            select(Portfolio).where(Portfolio.owner_telegram_id == owner_telegram_id).order_by(Portfolio.id)
        ))

    def get_for_owner(self, portfolio_id: int, owner_telegram_id: int) -> Portfolio | None:
        return self.session.scalar(select(Portfolio).where(
            Portfolio.id == portfolio_id,
            Portfolio.owner_telegram_id == owner_telegram_id,
        ))

    def create(self, display_name: str, owner_telegram_id: int | None = None) -> Portfolio:
        portfolio = Portfolio(name=display_name, owner_telegram_id=owner_telegram_id)
        self.session.add(portfolio)
        self.session.flush()
        return portfolio

    def rename(self, portfolio: Portfolio, display_name: str) -> Portfolio:
        portfolio.name = display_name
        self.session.flush()
        return portfolio

    def delete(self, portfolio: Portfolio) -> None:
        """Delete a portfolio and its portfolio-scoped records."""

        for model in (TelegramImport, TelegramChannel, TelegramConfig, PortfolioCurrencySetting, MonthlyExpense, Item):
            self.session.execute(delete(model).where(model.portfolio_id == portfolio.id))
        self.session.delete(portfolio)
        self.session.flush()

    def photo_paths_for_portfolio(self, portfolio_id: int) -> list[str]:
        return [
            path
            for path in self.session.scalars(
                select(Item.photo_path).where(
                    Item.portfolio_id == portfolio_id,
                    Item.photo_path.is_not(None),
                )
            )
            if path
        ]

    def delete_all_for_owner(self, owner_telegram_id: int) -> list[str]:
        """Delete all tenant records and return their photo paths for cleanup."""

        portfolios = self.list_for_owner(owner_telegram_id)
        if not portfolios:
            return []
        portfolio_ids = [portfolio.id for portfolio in portfolios]
        photo_paths = [
            path
            for portfolio_id in portfolio_ids
            for path in self.photo_paths_for_portfolio(portfolio_id)
        ]
        for portfolio in portfolios:
            self.delete(portfolio)
        return photo_paths

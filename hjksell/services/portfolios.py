"""Portfolio display-name business rules."""

from __future__ import annotations

from ..database.models import Portfolio
from ..repositories.portfolio_repository import PortfolioRepository


class PortfolioService:
    MAX_DISPLAY_NAME_LENGTH = 24

    def __init__(self, repository: PortfolioRepository) -> None:
        self.repository = repository

    def rename(self, portfolio: Portfolio, display_name: str) -> Portfolio:
        normalized = display_name.strip()
        if not normalized:
            raise ValueError("Название портфеля не может быть пустым.")
        if len(normalized) > self.MAX_DISPLAY_NAME_LENGTH:
            raise ValueError("Название портфеля не может быть длиннее 24 символов.")
        return self.repository.rename(portfolio, normalized)

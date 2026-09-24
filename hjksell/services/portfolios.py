"""Portfolio display-name business rules."""

from __future__ import annotations

from ..database.models import Portfolio
from ..repositories.portfolio_repository import PortfolioRepository


class PortfolioService:
    MAX_DISPLAY_NAME_LENGTH = 24

    def __init__(self, repository: PortfolioRepository) -> None:
        self.repository = repository

    def _normalized_name(
        self,
        display_name: str,
        *,
        current_id: int | None = None,
        owner_telegram_id: int | None = None,
    ) -> str:
        normalized = display_name.strip()
        if not normalized:
            raise ValueError("Название портфеля не может быть пустым.")
        if len(normalized) > self.MAX_DISPLAY_NAME_LENGTH:
            raise ValueError("Название портфеля не может быть длиннее 24 символов.")
        if any(
            existing.id != current_id and existing.name.casefold() == normalized.casefold()
            for existing in (
                self.repository.list_all()
                if owner_telegram_id is None
                else self.repository.list_for_owner(owner_telegram_id)
            )
        ):
            raise ValueError("Портфель с таким названием уже существует.")
        return normalized

    def create(self, display_name: str, owner_telegram_id: int | None = None) -> Portfolio:
        return self.repository.create(
            self._normalized_name(display_name, owner_telegram_id=owner_telegram_id),
            owner_telegram_id,
        )

    def rename(self, portfolio: Portfolio, display_name: str) -> Portfolio:
        normalized = self._normalized_name(
            display_name,
            current_id=portfolio.id,
            owner_telegram_id=portfolio.owner_telegram_id,
        )
        return self.repository.rename(portfolio, normalized)

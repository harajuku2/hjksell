"""Use cases for creating, selling, and updating catalogue items."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from ..database.models import Item, ItemStatus
from ..repositories.item_repository import ItemRepository
from ..repositories.settings_repository import SettingsRepository
from .finance import calculate_cost, parse_decimal, rate


class ItemService:
    def __init__(self, repository: ItemRepository, settings: SettingsRepository) -> None:
        self.repository = repository
        self.settings = settings

    def create_item(
        self,
        portfolio_id: int,
        purchase_price_pln: Decimal,
        purchase_date: date,
        photo_path: str | None = None,
    ) -> Item:
        if purchase_price_pln <= 0:
            raise ValueError("Цена покупки должна быть больше нуля.")
        exchange_rate = self.settings.current_exchange_rate()
        item = Item(
            portfolio_id=portfolio_id,
            photo_path=photo_path,
            purchase_date=purchase_date,
            purchase_price_pln=purchase_price_pln.quantize(Decimal("0.01")),
            exchange_rate=rate(exchange_rate),
            cost_byn=calculate_cost(purchase_price_pln, exchange_rate),
            status=ItemStatus.IN_STOCK.value,
        )
        return self.repository.add_item(item)

    def create_from_text(
        self, portfolio_id: int, price_text: str, purchase_date: date, photo_path: str | None = None
    ) -> Item:
        return self.create_item(
            portfolio_id, parse_decimal(price_text, field_name="цену PLN", positive=True), purchase_date, photo_path
        )

    def sell(self, item: Item, sale_price_text: str, sale_date: date | None = None) -> Item:
        sale_price = parse_decimal(sale_price_text, field_name="цену продажи", positive=True)
        if item.deleted_at is not None:
            raise ValueError("Удалённую вещь нельзя продать.")
        effective_sale_date = item.sale_date or sale_date or date.today()
        return self.repository.sale(item, sale_price.quantize(Decimal("0.01")), effective_sale_date)

"""Use cases for creating, selling, and updating catalogue items."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from ..database.models import Item, ItemStatus
from ..repositories.item_repository import ItemRepository
from ..repositories.settings_repository import SettingsRepository
from .finance import calculate_cost, money, parse_decimal, rate


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
        if purchase_price_pln < 0:
            raise ValueError("Цена покупки не может быть отрицательной.")
        profile = self.settings.currency_profile(portfolio_id)
        exchange_rate = profile.exchange_rate
        purchase_expense = money(
            profile.automatic_expense_amount * profile.automatic_expense_purchase_rate
        )
        item = Item(
            portfolio_id=portfolio_id,
            photo_path=photo_path,
            purchase_date=purchase_date,
            purchase_price_pln=purchase_price_pln.quantize(Decimal("0.01")),
            purchase_expense=purchase_expense,
            purchase_currency=profile.purchase_currency,
            exchange_rate=rate(exchange_rate),
            cost_byn=calculate_cost(purchase_price_pln, exchange_rate, purchase_expense),
            sale_currency=profile.sale_currency,
            status=ItemStatus.IN_STOCK.value,
        )
        return self.repository.add_item(item)

    def create_from_text(
        self, portfolio_id: int, price_text: str, purchase_date: date, photo_path: str | None = None
    ) -> Item:
        return self.create_item(
            portfolio_id, parse_decimal(price_text, field_name="цену покупки", non_negative=True), purchase_date, photo_path
        )

    def sell(self, item: Item, sale_price_text: str, sale_date: date | None = None) -> Item:
        if item.deleted_at is not None:
            raise ValueError("Удалённую вещь нельзя продать.")
        if not sale_price_text.strip():
            return self.repository.cancel_sale(item)
        sale_price = parse_decimal(sale_price_text, field_name="цену продажи")
        if sale_price < 0:
            raise ValueError("Цена продажи не может быть отрицательной.")
        effective_sale_date = item.sale_date or sale_date or date.today()
        return self.repository.sale(item, sale_price.quantize(Decimal("0.01")), effective_sale_date)

    def update_purchase_details(
        self,
        item: Item,
        *,
        purchase_price_text: str | None = None,
        purchase_expense_text: str | None = None,
        purchase_date: date | None = None,
        exchange_rate_text: str | None = None,
    ) -> Item:
        if item.deleted_at is not None:
            raise ValueError("Удалённую вещь нельзя изменить.")
        if (
            purchase_price_text is None
            and purchase_expense_text is None
            and purchase_date is None
            and exchange_rate_text is None
        ):
            raise ValueError("Не переданы данные для изменения вещи.")
        purchase_price = (
            item.purchase_price_pln
            if purchase_price_text is None
            else parse_decimal(purchase_price_text, field_name="цену покупки", non_negative=True)
        ).quantize(Decimal("0.01"))
        effective_date = purchase_date or item.purchase_date
        purchase_expense = (
            item.purchase_expense
            if purchase_expense_text is None
            else (
                Decimal("0.00")
                if not purchase_expense_text.strip()
                else parse_decimal(purchase_expense_text, field_name="расход", non_negative=True).quantize(Decimal("0.01"))
            )
        )
        exchange_rate = (
            item.exchange_rate
            if exchange_rate_text is None
            else rate(parse_decimal(exchange_rate_text, field_name="курс", positive=True))
        )
        return self.repository.update_purchase_details(
            item,
            purchase_price,
            purchase_expense,
            effective_date,
            exchange_rate,
            calculate_cost(purchase_price, exchange_rate, purchase_expense),
        )

    def update_sale_date(self, item: Item, sale_date: date) -> Item:
        if item.deleted_at is not None:
            raise ValueError("Удалённую вещь нельзя изменить.")
        if item.sale_price_byn is None:
            raise ValueError("У вещи нет завершённой продажи.")
        return self.repository.update_sale_date(item, sale_date)

"""Catalog response assembly over the existing HJKsell core."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

from sqlalchemy.orm import Session

from ..database.models import Item
from ..repositories.item_repository import ItemRepository
from ..repositories.settings_repository import SettingsRepository
from ..services.analytics import AnalyticsService, MonthlyMetrics
from ..services.catalog import item_matches_catalog_filter
from ..services.finance import item_metrics


def decimal_text(value: Decimal | None, places: str = "0.01") -> str | None:
    """Serialize Decimal values without crossing the API boundary as floats."""

    return None if value is None else format(value.quantize(Decimal(places)), "f")


class CatalogQueryService:
    def __init__(self, session: Session, media_root: Path) -> None:
        self.repository = ItemRepository(session)
        self.settings = SettingsRepository(session)
        self.analytics = AnalyticsService(self.repository)
        self.media_root = media_root.resolve()

    def catalog(
        self,
        portfolio_id: int,
        filter_key: str,
        year: int | None = None,
        month: int | None = None,
    ) -> dict:
        all_items = self.repository.active_items(portfolio_id)
        visible_items = [item for item in all_items if item_matches_catalog_filter(item, filter_key)]
        periods = {(item.purchase_date.year, item.purchase_date.month) for item in all_items}
        periods.update(
            (row_year, row_month)
            for row_year, row_month, _expenses, _other_income, _advertising
            in self.repository.all_monthly_financials(portfolio_id)
        )
        today = date.today()
        periods.add((today.year, today.month))
        if year is not None and month is not None:
            periods = {(year, month)}

        return {
            "portfolio_id": portfolio_id,
            "exchange_rate": decimal_text(self.settings.current_exchange_rate(), "0.0001"),
            "filter": filter_key,
            "months": [
                self._month(portfolio_id, period_year, period_month, visible_items)
                for period_year, period_month in sorted(periods, reverse=True)
            ],
        }

    def item(self, item: Item) -> dict:
        metrics = item_metrics(item.sale_price_byn, item.cost_byn)
        return {
            "id": item.id,
            "portfolio_id": item.portfolio_id,
            "photo_url": self._photo_url(item.photo_path),
            "purchase_date": item.purchase_date.isoformat(),
            "purchase_price_pln": decimal_text(item.purchase_price_pln),
            "exchange_rate": decimal_text(item.exchange_rate, "0.0001"),
            "cost_byn": decimal_text(item.cost_byn),
            "sale_price_byn": decimal_text(item.sale_price_byn),
            "sale_date": item.sale_date.isoformat() if item.sale_date else None,
            "sale_state": self._sale_state(item),
            "profit": decimal_text(metrics.profit),
            "x": decimal_text(metrics.x),
            "roi": decimal_text(metrics.roi),
            "days_to_sale": (item.sale_date - item.purchase_date).days if item.sale_date else None,
        }

    def _month(self, portfolio_id: int, year: int, month: int, items: list[Item]) -> dict:
        metrics = self.analytics.monthly_metrics(portfolio_id, year, month)
        return {
            "year": year,
            "month": month,
            "metrics": self._metrics(metrics),
            "values": {
                "expenses": decimal_text(metrics.expenses),
                "other_income": decimal_text(metrics.other_income),
                "advertising": decimal_text(metrics.advertising),
            },
            "items": [
                self.item(item)
                for item in items
                if item.purchase_date.year == year and item.purchase_date.month == month
            ],
        }

    @staticmethod
    def _metrics(metrics: MonthlyMetrics) -> dict:
        return {
            "invested": decimal_text(metrics.invested),
            "purchased_count": metrics.purchased_count,
            "revenue": decimal_text(metrics.revenue),
            "sold_count": metrics.sold_count,
            "average_x": decimal_text(metrics.average_x),
            "roi": decimal_text(metrics.roi),
            "net_profit": decimal_text(metrics.net_profit),
        }

    @staticmethod
    def _sale_state(item: Item) -> str:
        if item.sale_price_byn is None:
            return "in_stock"
        if item.sale_price_byn == 0:
            return "no_revenue"
        return "sold"

    def _photo_url(self, photo_path: str | None) -> str | None:
        if not photo_path:
            return None
        path = Path(photo_path).resolve()
        if path.parent != self.media_root or not path.is_file():
            return None
        return f"/api/dev-media/{path.name}"

"""Reusable Catalog behavior shared by desktop and web adapters."""

from __future__ import annotations

from ..database.models import Item


CATALOG_FILTERS = {"all", "stock", "sold", "no_revenue"}


def item_matches_catalog_filter(item: Item, filter_key: str) -> bool:
    """Return whether an active Item belongs to the requested Catalog filter."""

    sale_price = item.sale_price_byn
    if filter_key == "stock":
        return sale_price is None
    if filter_key == "sold":
        return sale_price is not None and sale_price > 0
    if filter_key == "no_revenue":
        return sale_price == 0
    return True

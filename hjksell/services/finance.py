"""Decimal-only financial calculations."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

CENT = Decimal("0.01")
FOUR_PLACES = Decimal("0.0001")


def money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def rate(value: Decimal) -> Decimal:
    return value.quantize(FOUR_PLACES, rounding=ROUND_HALF_UP)


def calculate_cost(purchase_price_pln: Decimal, exchange_rate: Decimal) -> Decimal:
    return money(purchase_price_pln * exchange_rate)


def calculate_profit(sale_price_byn: Decimal | None, cost_byn: Decimal) -> Decimal | None:
    return None if sale_price_byn is None else money(sale_price_byn - cost_byn)


def calculate_x(sale_price_byn: Decimal | None, cost_byn: Decimal) -> Decimal | None:
    if sale_price_byn is None or cost_byn == 0:
        return None
    return (sale_price_byn / cost_byn).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def calculate_roi(sale_price_byn: Decimal | None, cost_byn: Decimal) -> Decimal | None:
    profit = calculate_profit(sale_price_byn, cost_byn)
    if profit is None or cost_byn == 0:
        return None
    return (profit / cost_byn * Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class ItemMetrics:
    profit: Decimal | None
    x: Decimal | None
    roi: Decimal | None


def item_metrics(sale_price_byn: Decimal | None, cost_byn: Decimal) -> ItemMetrics:
    return ItemMetrics(
        profit=calculate_profit(sale_price_byn, cost_byn),
        x=calculate_x(sale_price_byn, cost_byn),
        roi=calculate_roi(sale_price_byn, cost_byn),
    )

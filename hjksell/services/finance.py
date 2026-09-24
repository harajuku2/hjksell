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


def parse_decimal(
    value: str,
    *,
    field_name: str = "значение",
    positive: bool = False,
    non_negative: bool = False,
) -> Decimal:
    """Parse user-entered decimal text, accepting the comma decimal separator."""

    text = value.strip().replace(",", ".")
    if not text:
        raise ValueError(f"Введите {field_name}.")
    try:
        parsed = Decimal(text)
    except Exception as exc:
        raise ValueError(f"Некорректное {field_name}.") from exc
    if not parsed.is_finite():
        raise ValueError(f"Некорректное {field_name}.")
    if positive and parsed <= 0:
        raise ValueError(f"{field_name.capitalize()} должно быть больше нуля.")
    if non_negative and parsed < 0:
        raise ValueError(f"{field_name.capitalize()} не может быть отрицательным.")
    return parsed


def calculate_cost(
    purchase_price_pln: Decimal,
    exchange_rate: Decimal,
    purchase_expense: Decimal = Decimal("0.00"),
) -> Decimal:
    """Calculate historical cost including the item's purchase-currency expense."""

    return money((purchase_price_pln + purchase_expense) * exchange_rate)


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

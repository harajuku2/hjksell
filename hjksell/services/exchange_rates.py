"""Official exchange-rate lookup and Decimal cross-rate calculation."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import httpx

from ..repositories.settings_repository import PURCHASE_CURRENCIES
from .finance import rate

NBRB_DAILY_RATES_URL = "https://api.nbrb.by/exrates/rates?periodicity=0"


class OfficialExchangeRateService:
    """Resolve a purchase-to-sale rate from official NBRB daily rates."""

    def __init__(self, client: httpx.Client | None = None) -> None:
        self._client = client

    def latest(self, purchase_currency: str, sale_currency: str) -> tuple[Decimal, date]:
        purchase = purchase_currency.strip().upper()
        sale = sale_currency.strip().upper()
        if purchase not in PURCHASE_CURRENCIES or sale not in PURCHASE_CURRENCIES:
            raise ValueError("Выбранная валютная пара не поддерживается.")
        if purchase == sale:
            return Decimal("1.0000"), date.today()

        owns_client = self._client is None
        # A stale system proxy must not block the local app from reaching the official API.
        client = self._client or httpx.Client(timeout=8.0, trust_env=False)
        try:
            response = client.get(NBRB_DAILY_RATES_URL)
            response.raise_for_status()
            payload = response.json()
        finally:
            if owns_client:
                client.close()

        unit_rates: dict[str, Decimal] = {"BYN": Decimal("1")}
        rate_date: date | None = None
        for entry in payload:
            code = str(entry.get("Cur_Abbreviation", "")).upper()
            if not code:
                continue
            scale = Decimal(str(entry["Cur_Scale"]))
            official = Decimal(str(entry["Cur_OfficialRate"]))
            unit_rates[code] = official / scale
            if rate_date is None and entry.get("Date"):
                rate_date = date.fromisoformat(str(entry["Date"])[:10])

        missing = [code for code in (purchase, sale) if code not in unit_rates]
        if missing:
            raise ValueError(f"Официальный курс для {', '.join(missing)} сейчас недоступен.")
        return rate(unit_rates[purchase] / unit_rates[sale]), rate_date or date.today()

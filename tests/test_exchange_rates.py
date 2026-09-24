"""Regression coverage for official cross-currency rates."""

from decimal import Decimal

from hjksell.repositories.settings_repository import PURCHASE_CURRENCIES, SALE_CURRENCIES
from hjksell.services.exchange_rates import OfficialExchangeRateService


class FakeResponse:
    def raise_for_status(self) -> None:
        return None

    def json(self) -> list[dict]:
        return [
            {"Date": "2026-09-16T00:00:00", "Cur_Abbreviation": "PLN", "Cur_Scale": 10, "Cur_OfficialRate": 8.0524},
            {"Date": "2026-09-16T00:00:00", "Cur_Abbreviation": "USD", "Cur_Scale": 1, "Cur_OfficialRate": 3.0286},
            {"Date": "2026-09-16T00:00:00", "Cur_Abbreviation": "CNY", "Cur_Scale": 10, "Cur_OfficialRate": 4.5162},
        ]


class FakeClient:
    def get(self, url: str) -> FakeResponse:
        assert url.endswith("periodicity=0")
        return FakeResponse()


def test_official_rate_service_respects_scale_and_calculates_cross_rate() -> None:
    service = OfficialExchangeRateService(FakeClient())

    pln_to_byn, effective_date = service.latest("PLN", "BYN")
    cny_to_usd, _ = service.latest("CNY", "USD")

    assert pln_to_byn == Decimal("0.8052")
    assert cny_to_usd == Decimal("0.1491")
    assert effective_date.isoformat() == "2026-09-16"


def test_main_currency_selectors_share_the_full_supported_currency_set() -> None:
    assert SALE_CURRENCIES == PURCHASE_CURRENCIES

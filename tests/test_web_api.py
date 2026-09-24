"""API coverage for the isolated local web skeleton."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from hjksell.repositories.item_repository import ItemRepository
from hjksell.repositories.telegram_repository import TelegramRepository
from hjksell.web.app import create_app
from hjksell.web.config import web_dev_paths


@pytest.fixture
def web_client(tmp_path: Path):
    paths = web_dev_paths(tmp_path / "web-development")
    app = create_app(paths)
    with TestClient(app) as client:
        yield client, app, paths
    app.state.engine.dispose()


def portfolio_ids(client: TestClient) -> list[int]:
    response = client.get("/api/portfolios")
    assert response.status_code == 200
    return [portfolio["id"] for portfolio in response.json()]


def create_item(
    client: TestClient,
    portfolio_id: int,
    price: str = "100",
    purchased: str = "2026-09-01",
) -> dict:
    response = client.post(
        "/api/items",
        json={
            "portfolio_id": portfolio_id,
            "purchase_price_pln": price,
            "purchase_date": purchased,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def sale(client: TestClient, portfolio_id: int, item_id: int, price: str) -> dict:
    response = client.put(
        f"/api/items/{item_id}/sale",
        json={"portfolio_id": portfolio_id, "sale_price_byn": price, "sale_date": "2026-09-10"},
    )
    assert response.status_code == 200, response.text
    return response.json()


def selected_month(client: TestClient, portfolio_id: int, year: int = 2026, month: int = 9, filter_key: str = "all") -> dict:
    response = client.get(
        "/api/catalog",
        params={"portfolio_id": portfolio_id, "filter": filter_key, "year": year, "month": month},
    )
    assert response.status_code == 200, response.text
    return response.json()["months"][0]


def test_health_and_portfolio_listing_do_not_expose_telegram_state(web_client) -> None:
    client, _app, _paths = web_client
    health = client.get("/api/health")
    assert health.status_code == 200
    assert health.json() == {
        "status": "ok",
        "data_scope": "isolated-web-development",
        "data_deletion_enabled": False,
    }
    portfolios = client.get("/api/portfolios").json()
    assert len(portfolios) == 2
    assert all(set(portfolio) == {"id", "name"} for portfolio in portfolios)
    assert "token" not in (health.text + str(portfolios)).lower()


def test_portfolio_can_be_renamed_without_changing_identity(web_client) -> None:
    client, _app, _paths = web_client
    portfolio_id = portfolio_ids(client)[0]
    response = client.put(f"/api/portfolios/{portfolio_id}", json={"name": "Мой каталог"})
    assert response.status_code == 200
    assert response.json() == {"id": portfolio_id, "name": "Мой каталог"}
    assert {portfolio["id"] for portfolio in client.get("/api/portfolios").json()} == set(portfolio_ids(client))
    too_long = client.put(f"/api/portfolios/{portfolio_id}", json={"name": "x" * 25})
    assert too_long.status_code == 422


def test_portfolio_can_be_created_as_an_independent_empty_workspace(web_client) -> None:
    client, _app, _paths = web_client
    existing_id = portfolio_ids(client)[0]
    create_item(client, existing_id, "100")

    response = client.post("/api/portfolios", json={"name": "Новый магазин"})
    assert response.status_code == 201, response.text
    created = response.json()
    assert created["id"] not in portfolio_ids(client)[:2]
    assert created["name"] == "Новый магазин"

    month = selected_month(client, created["id"])
    assert month["items"] == []
    assert month["metrics"]["purchased_count"] == 0
    telegram = client.get("/api/telegram/status", params={"portfolio_id": created["id"]})
    assert telegram.status_code == 200
    assert telegram.json()["configured"] is False
    assert telegram.json()["channel_id"] is None

    duplicate = client.post("/api/portfolios", json={"name": "новый магазин"})
    assert duplicate.status_code == 422


def test_portfolio_can_be_deleted_with_its_scoped_data(web_client) -> None:
    client, _app, _paths = web_client
    response = client.post("/api/portfolios", json={"name": "Удаляемый магазин"})
    assert response.status_code == 201
    portfolio_id = response.json()["id"]
    create_item(client, portfolio_id, "100")
    values = client.put(
        "/api/monthly-values",
        json={
            "portfolio_id": portfolio_id,
            "year": 2026,
            "month": 9,
            "expenses": "25",
            "other_income": "0",
            "advertising": "0",
        },
    )
    assert values.status_code == 200

    deleted = client.delete(f"/api/portfolios/{portfolio_id}")
    assert deleted.status_code == 200, deleted.text
    assert deleted.json() == {"id": portfolio_id, "name": "Удаляемый магазин"}
    assert portfolio_id not in portfolio_ids(client)
    assert client.get("/api/catalog", params={"portfolio_id": portfolio_id}).status_code == 404

    protected = client.delete(f"/api/portfolios/{portfolio_ids(client)[0]}")
    assert protected.status_code == 422


def test_analytics_endpoint_uses_portfolio_scoped_core_metrics(web_client) -> None:
    client, _app, _paths = web_client
    portfolio_id, other_id = portfolio_ids(client)
    assert client.put("/api/settings/exchange-rate", json={"rate": "1.0000"}).status_code == 200
    item = create_item(client, portfolio_id, "100")
    sale(client, portfolio_id, item["id"], "200")
    values = client.put(
        "/api/monthly-values",
        json={
            "portfolio_id": portfolio_id,
            "year": 2026,
            "month": 9,
            "expenses": "25",
            "other_income": "10",
            "advertising": "0",
        },
    )
    assert values.status_code == 200

    response = client.get(
        "/api/analytics",
        params={"portfolio_id": portfolio_id, "period": "current_month"},
    )
    assert response.status_code == 200, response.text
    report = response.json()
    assert report["period"] == {"start": "2026-09-01", "end": "2026-09-30"}
    assert report["metrics"]["revenue"] == "200.00"
    assert report["metrics"]["realized_profit"] == "100.00"
    assert report["metrics"]["net_profit"] == "85.00"
    assert report["metrics"]["sold_count"] == 1

    month = selected_month(client, portfolio_id)
    assert month["metrics"]["realized_profit"] == "100.00"
    assert month["metrics"]["total_profit"] == "85.00"

    other = client.get("/api/analytics", params={"portfolio_id": other_id}).json()
    assert other["metrics"]["revenue"] == "0.00"
    assert other["metrics"]["sold_count"] == 0


def test_web_telegram_config_is_portfolio_scoped_and_hides_token(web_client, monkeypatch) -> None:
    client, app, _paths = web_client
    portfolio_id = portfolio_ids(client)[0]
    monkeypatch.setattr(app.state.telegram_manager, "reconfigure", lambda _portfolio_id: None)

    saved = client.put(
        "/api/telegram/config",
        json={"portfolio_id": portfolio_id, "token": "123:secret-token", "channel_id": "-100123"},
    )
    assert saved.status_code == 200, saved.text
    assert "secret-token" not in saved.text
    assert saved.json()["configured"] is True
    assert saved.json()["channel_id"] == "-100123"

    status = client.get("/api/telegram/status", params={"portfolio_id": portfolio_id})
    assert status.status_code == 200
    assert "secret-token" not in status.text
    assert status.json()["configured"] is True

    cleared = client.delete("/api/telegram/config", params={"portfolio_id": portfolio_id})
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["configured"] is False
    assert cleared.json()["channel_id"] is None
    with app.state.session_factory() as session:
        telegram = TelegramRepository(session)
        assert telegram.token(portfolio_id) is None
        assert telegram.offset(portfolio_id) is None
        assert not [channel for channel in telegram.channels() if channel.portfolio_id == portfolio_id]


def test_web_telegram_token_validation_uses_api_without_persisting_token(web_client, monkeypatch) -> None:
    client, _app, _paths = web_client

    class FakeTelegramClient:
        def __init__(self, token: str) -> None:
            assert token == "123:secret-token"

        def validate_token(self) -> dict:
            return {"username": "hjk_bot", "first_name": "HJKsell"}

        def close(self) -> None:
            pass

    monkeypatch.setattr("hjksell.web.app.TelegramApiClient", FakeTelegramClient)
    response = client.post("/api/telegram/validate", json={"token": "123:secret-token"})
    assert response.status_code == 200
    assert response.json() == {"valid": True, "username": "hjk_bot", "name": "HJKsell"}
    assert "secret-token" not in response.text


def test_free_item_is_valid_and_negative_purchase_is_rejected(web_client) -> None:
    client, _app, _paths = web_client
    portfolio_id = portfolio_ids(client)[0]
    free_item = create_item(client, portfolio_id, "0")
    assert free_item["purchase_price_pln"] == "0.00"
    assert free_item["cost_byn"] == "0.00"
    sold = sale(client, portfolio_id, free_item["id"], "100")
    assert sold["profit"] == "100.00"
    assert sold["x"] is None
    assert sold["roi"] is None

    rejected = client.post(
        "/api/items",
        json={"portfolio_id": portfolio_id, "purchase_price_pln": "-1", "purchase_date": "2026-09-01"},
    )
    assert rejected.status_code == 422


def test_historical_fx_is_preserved_and_money_stays_string_serialized(web_client) -> None:
    client, _app, _paths = web_client
    portfolio_id = portfolio_ids(client)[0]
    assert client.put("/api/settings/exchange-rate", json={"rate": "0.8700"}).status_code == 200
    first = create_item(client, portfolio_id, "100")
    assert client.put("/api/settings/exchange-rate", json={"rate": "0.9000"}).status_code == 200
    second = create_item(client, portfolio_id, "100")

    assert first["exchange_rate"] == "0.8700"
    assert first["cost_byn"] == "87.00"
    assert second["exchange_rate"] == "0.9000"
    assert second["cost_byn"] == "90.00"
    assert isinstance(first["purchase_price_pln"], str)
    assert isinstance(first["cost_byn"], str)


def test_portfolio_currency_profile_applies_only_to_new_items(web_client) -> None:
    client, _app, _paths = web_client
    portfolio_id, other_id = portfolio_ids(client)

    initial = client.get("/api/settings/currencies", params={"portfolio_id": portfolio_id})
    assert initial.json() == {
        "portfolio_id": portfolio_id,
        "purchase_currency": "PLN",
        "sale_currency": "BYN",
        "exchange_rate": "0.8500",
    }
    changed = client.put(
        "/api/settings/currencies",
        json={
            "portfolio_id": portfolio_id,
            "purchase_currency": "CNY",
            "sale_currency": "USD",
            "rate": "0.1390",
        },
    )
    assert changed.status_code == 200, changed.text
    first = create_item(client, portfolio_id, "100")
    assert first["purchase_currency"] == "CNY"
    assert first["sale_currency"] == "USD"
    assert first["exchange_rate"] == "0.1390"
    assert first["cost_byn"] == "13.90"

    purchase_change = client.put(
        "/api/settings/currencies",
        json={
            "portfolio_id": portfolio_id,
            "purchase_currency": "EUR",
            "sale_currency": "USD",
            "rate": "1.2500",
        },
    )
    assert purchase_change.status_code == 200, purchase_change.text
    second = create_item(client, portfolio_id, "10")
    assert second["purchase_currency"] == "EUR"
    assert second["sale_currency"] == "USD"
    assert second["cost_byn"] == "12.50"

    old_item = next(item for item in selected_month(client, portfolio_id)["items"] if item["id"] == first["id"])
    assert old_item["purchase_currency"] == "CNY"
    assert old_item["sale_currency"] == "USD"
    assert old_item["exchange_rate"] == "0.1390"
    assert client.get("/api/settings/currencies", params={"portfolio_id": other_id}).json()["purchase_currency"] == "PLN"

    mixed_sale_currency = client.put(
        "/api/settings/currencies",
        json={
            "portfolio_id": portfolio_id,
            "purchase_currency": "EUR",
            "sale_currency": "EUR",
            "rate": "1.0000",
        },
    )
    assert mixed_sale_currency.status_code == 422
    assert "пустом портфеле" in mixed_sale_currency.json()["detail"]


def test_automatic_expense_applies_only_to_new_items_and_uses_a_saved_cross_rate(web_client, monkeypatch) -> None:
    client, _app, _paths = web_client
    portfolio_id = portfolio_ids(client)[0]
    before = create_item(client, portfolio_id, "100")

    class FakeRateService:
        def latest(self, source: str, target: str):
            assert (source, target) == ("USD", "PLN")
            return Decimal("3.5000"), date(2026, 9, 21)

    monkeypatch.setattr("hjksell.web.app.OfficialExchangeRateService", FakeRateService)
    saved = client.put(
        "/api/settings/automatic-expense",
        json={"portfolio_id": portfolio_id, "amount": "1", "expense_currency": "USD"},
    )
    assert saved.status_code == 200, saved.text
    assert saved.json() == {
        "portfolio_id": portfolio_id,
        "amount": "1.00",
        "expense_currency": "USD",
        "purchase_currency": "PLN",
        "purchase_rate": "3.5000",
    }

    after = create_item(client, portfolio_id, "100")
    assert before["purchase_expense"] == "0.00"
    assert before["cost_byn"] == "85.00"
    assert after["purchase_expense"] == "3.50"
    assert after["cost_byn"] == "87.98"

    manual = client.put(
        f"/api/items/{after['id']}",
        json={"portfolio_id": portfolio_id, "purchase_expense": "5"},
    )
    assert manual.status_code == 200, manual.text
    assert manual.json()["purchase_expense"] == "5.00"
    assert manual.json()["cost_byn"] == "89.25"


def test_latest_exchange_rate_endpoint_uses_official_rate_service(web_client, monkeypatch) -> None:
    client, _app, _paths = web_client

    class FakeRateService:
        def latest(self, purchase_currency: str, sale_currency: str):
            assert (purchase_currency, sale_currency) == ("JPY", "EUR")
            return Decimal("0.0056"), date(2026, 9, 16)

    monkeypatch.setattr("hjksell.web.app.OfficialExchangeRateService", FakeRateService)
    response = client.get(
        "/api/exchange-rates/latest",
        params={"purchase_currency": "JPY", "sale_currency": "EUR"},
    )
    assert response.status_code == 200
    assert response.json() == {
        "purchase_currency": "JPY",
        "sale_currency": "EUR",
        "exchange_rate": "0.0056",
        "effective_date": "2026-09-16",
        "source": "Национальный банк Республики Беларусь",
    }


def test_new_manual_items_are_returned_newest_first(web_client) -> None:
    client, _app, _paths = web_client
    portfolio_id = portfolio_ids(client)[0]
    older = create_item(client, portfolio_id, "10", "2026-09-16")
    newer = create_item(client, portfolio_id, "20", "2026-09-16")

    items = selected_month(client, portfolio_id)["items"]
    assert [item["id"] for item in items[:2]] == [newer["id"], older["id"]]


def test_catalog_filters_distinguish_none_zero_and_positive_sales(web_client) -> None:
    client, _app, _paths = web_client
    portfolio_id = portfolio_ids(client)[0]
    stock = create_item(client, portfolio_id, "10")
    zero = create_item(client, portfolio_id, "20")
    positive = create_item(client, portfolio_id, "30")
    sale(client, portfolio_id, zero["id"], "0")
    sale(client, portfolio_id, positive["id"], "50")

    assert {item["id"] for item in selected_month(client, portfolio_id, filter_key="stock")["items"]} == {stock["id"]}
    assert {item["id"] for item in selected_month(client, portfolio_id, filter_key="sold")["items"]} == {positive["id"]}
    assert {item["id"] for item in selected_month(client, portfolio_id, filter_key="no_revenue")["items"]} == {zero["id"]}

    cancelled = sale(client, portfolio_id, zero["id"], "")
    assert cancelled["sale_price_byn"] is None
    assert cancelled["sale_date"] is None
    assert cancelled["sale_state"] == "in_stock"


def test_sale_date_is_preserved_during_regular_inline_edit(web_client) -> None:
    client, _app, _paths = web_client
    portfolio_id = portfolio_ids(client)[0]
    item = create_item(client, portfolio_id)
    first_sale = sale(client, portfolio_id, item["id"], "100")
    changed = client.put(
        f"/api/items/{item['id']}/sale",
        json={"portfolio_id": portfolio_id, "sale_price_byn": "120", "sale_date": "2026-09-15"},
    ).json()
    assert changed["sale_date"] == first_sale["sale_date"] == "2026-09-10"


def test_item_purchase_details_and_sale_date_can_be_edited(web_client) -> None:
    client, _app, _paths = web_client
    portfolio_id, other_portfolio = portfolio_ids(client)
    item = create_item(client, portfolio_id, "100", "2026-09-01")
    sale(client, portfolio_id, item["id"], "100")

    changed = client.put(
        f"/api/items/{item['id']}",
        json={
            "portfolio_id": portfolio_id,
            "purchase_price_pln": "20,50",
            "purchase_date": "2026-09-03",
            "exchange_rate": "0.9000",
        },
    )
    assert changed.status_code == 200, changed.text
    assert changed.json()["purchase_price_pln"] == "20.50"
    assert changed.json()["purchase_date"] == "2026-09-03"
    assert changed.json()["exchange_rate"] == "0.9000"
    assert changed.json()["cost_byn"] == "18.45"
    assert changed.json()["profit"] == "81.55"

    expense_added = client.put(
        f"/api/items/{item['id']}",
        json={"portfolio_id": portfolio_id, "purchase_expense": "10"},
    )
    assert expense_added.status_code == 200, expense_added.text
    assert expense_added.json()["purchase_expense"] == "10.00"
    assert expense_added.json()["cost_byn"] == "27.45"
    assert expense_added.json()["profit"] == "72.55"
    assert expense_added.json()["x"] == "3.64"
    assert expense_added.json()["roi"] == "264.30"

    expense_cleared = client.put(
        f"/api/items/{item['id']}",
        json={"portfolio_id": portfolio_id, "purchase_expense": ""},
    )
    assert expense_cleared.status_code == 200, expense_cleared.text
    assert expense_cleared.json()["purchase_expense"] == "0.00"
    assert expense_cleared.json()["cost_byn"] == "18.45"
    assert expense_cleared.json()["profit"] == "81.55"

    sale_date = client.put(
        f"/api/items/{item['id']}/sale-date",
        json={"portfolio_id": portfolio_id, "sale_date": "2026-09-12"},
    )
    assert sale_date.status_code == 200, sale_date.text
    assert sale_date.json()["sale_date"] == "2026-09-12"

    wrong_portfolio = client.put(
        f"/api/items/{item['id']}",
        json={"portfolio_id": other_portfolio, "exchange_rate": "1.0000"},
    )
    assert wrong_portfolio.status_code == 404


def test_monthly_values_and_metrics_are_isolated_by_portfolio_and_month(web_client) -> None:
    client, _app, _paths = web_client
    first_portfolio, second_portfolio = portfolio_ids(client)
    create_item(client, first_portfolio, "100")
    update = {
        "portfolio_id": first_portfolio,
        "year": 2026,
        "month": 9,
        "expenses": "10",
        "other_income": "25",
        "advertising": "5",
    }
    response = client.put("/api/monthly-values", json=update)
    assert response.status_code == 200
    september = selected_month(client, first_portfolio)
    august = selected_month(client, first_portfolio, month=8)
    other_portfolio = selected_month(client, second_portfolio)
    assert september["values"] == {"expenses": "10.00", "other_income": "25.00", "advertising": "5.00"}
    assert september["metrics"]["revenue"] == "0.00"
    assert september["metrics"]["net_profit"] == "20.00"
    assert august["values"] == {"expenses": "0.00", "other_income": "0.00", "advertising": "0.00"}
    assert other_portfolio["values"] == {"expenses": "0.00", "other_income": "0.00", "advertising": "0.00"}


def test_item_mutations_require_matching_portfolio_identity(web_client) -> None:
    client, _app, _paths = web_client
    owner_id, other_id = portfolio_ids(client)
    item = create_item(client, owner_id)
    sale_response = client.put(
        f"/api/items/{item['id']}/sale",
        json={"portfolio_id": other_id, "sale_price_byn": "100"},
    )
    delete_response = client.delete(f"/api/items/{item['id']}", params={"portfolio_id": other_id})
    assert sale_response.status_code == 404
    assert delete_response.status_code == 404
    assert selected_month(client, owner_id)["items"][0]["sale_price_byn"] is None


def test_soft_delete_removes_item_from_catalog_and_metrics(web_client) -> None:
    client, _app, _paths = web_client
    portfolio_id = portfolio_ids(client)[0]
    item = create_item(client, portfolio_id)
    response = client.delete(f"/api/items/{item['id']}", params={"portfolio_id": portfolio_id})
    assert response.status_code == 200
    month = selected_month(client, portfolio_id)
    assert month["items"] == []
    assert month["metrics"]["purchased_count"] == 0


def test_development_photo_upload_and_media_route_are_confined(web_client) -> None:
    client, app, paths = web_client
    portfolio_id = portfolio_ids(client)[0]
    item = create_item(client, portfolio_id)
    png = b"\x89PNG\r\n\x1a\n" + b"development-fixture"
    uploaded = client.post(
        f"/api/items/{item['id']}/photo",
        params={"portfolio_id": portfolio_id, "filename": "fixture.png"},
        content=png,
        headers={"Content-Type": "image/png"},
    )
    assert uploaded.status_code == 200, uploaded.text
    photo_url = uploaded.json()["photo_url"]
    assert photo_url.startswith("/api/dev-media/")
    assert client.get(photo_url).content == png
    assert paths.photos.resolve() in Path(app.state.paths.photos).resolve().parents or paths.photos == app.state.paths.photos

    traversal = client.post(
        f"/api/items/{item['id']}/photo",
        params={"portfolio_id": portfolio_id, "filename": "../outside.png"},
        content=png,
        headers={"Content-Type": "image/png"},
    )
    assert traversal.status_code == 422
    assert client.get("/api/dev-media/..%2Foutside.png").status_code == 404
    wrong_type = client.post(
        f"/api/items/{item['id']}/photo",
        params={"portfolio_id": portfolio_id, "filename": "fake.png"},
        content=b"plain text",
        headers={"Content-Type": "image/png"},
    )
    assert wrong_type.status_code == 422


def test_catalog_never_exposes_a_photo_path_outside_dev_media(web_client, tmp_path: Path) -> None:
    client, app, _paths = web_client
    portfolio_id = portfolio_ids(client)[0]
    item = create_item(client, portfolio_id)
    outside = tmp_path / "outside.png"
    outside.write_bytes(b"not-user-data")
    with app.state.session_factory() as session:
        stored = ItemRepository(session).get(item["id"], portfolio_id)
        assert stored is not None
        ItemRepository(session).replace_photo(stored, str(outside))
        session.commit()
    returned = selected_month(client, portfolio_id)["items"][0]
    assert returned["photo_url"] is None
    assert str(outside) not in str(returned)


def test_static_catalog_uses_month_details_as_single_collapse_boundary(web_client) -> None:
    client, _app, _paths = web_client
    page = client.get("/")
    assert page.status_code == 200
    assert '<div class="header-actions">' not in page.text
    assert 'id="collapsedSummary"' in page.text
    script = client.get("/app.js").text
    assert '<details class="month"' in script
    assert '<div class="month-body">' in script
    assert "monthly-values" in script
    assert "group.items.map(itemHtml)" in script
    assert 'data-action="menu"' in script
    assert "portfolioNameInput" in script
    assert 'id="portfolioSelect"' in page.text
    assert 'id="createPortfolioButton"' in page.text
    assert 'id="deletePortfolioButton"' in page.text
    assert 'id="analyticsView"' in page.text
    assert 'id="telegramView"' in page.text
    assert 'id="newItemView"' in page.text
    assert 'id="telegramPortfolioPickerButton"' in page.text
    assert 'id="newItemPortfolioPickerButton"' in page.text
    assert 'id="settingsView"' in page.text
    assert 'id="automaticExpenseForm"' in page.text
    assert 'id="automaticExpensePortfolioPickerButton"' in page.text
    assert 'id="portfolioPickerButton"' in page.text
    assert 'id="analyticsPickerButton"' in page.text
    assert 'id="analyticsPortfolioPickerButton"' in page.text
    assert 'id="analyticsPortfolioSelect"' in page.text
    assert "analyticsGroups" in script
    assert "ПРИБЫЛЬ С ПРОДАЖ" in script
    assert 'id="mobileCatalogTab"' in page.text
    assert 'id="mobileAnalyticsTab"' in page.text
    assert 'id="mobileTelegramTab"' in page.text
    assert 'id="mobileNewItemTab"' in page.text
    assert 'id="mobileSettingsTab"' in page.text
    assert 'id="scrollTopButton"' in page.text
    assert 'id="currencyPanelClose"' in page.text
    assert "lastAnalyticsFingerprint" in script
    assert "renderGlassSelect" in script
    assert 'menu.classList.add("currency-option-menu")' not in script
    styles_response = client.get("/styles.css")
    assert styles_response.headers["cache-control"] == "no-store"
    assert "surface-reveal" in styles_response.text
    styles = styles_response.text
    assert ".currency-option-menu" in styles
    assert ".currency-select { position: static; }" in styles
    assert "Mobile pickers keep the compact catalog-menu scale" in styles
    assert "currency-menu-close + button[data-value]" in styles
    assert "catalog-user-backdrop.jpg" in styles
    assert "background: #0d0f14" in styles
    assert "background: #11131a" in styles
    assert "lastCatalogFingerprint" in script
    assert 'id="photoViewer"' in page.text
    assert 'data-action="view-photo"' in script
    assert "openPhotoViewer" in script
    assert "saleDrafts" in script
    assert "catalogIsBeingEdited" in script
    assert "telegramChannelDirty" in script
    assert "rateDirty" in script
    assert "rateInput.blur()" in script
    assert "openItemMenuId" in script
    assert "item-content" in script
    assert "collapsedSummaryHtml" in script
    assert "function orderMonthGroups" in script
    assert "const defaultOpen = false" in script
    assert "currentMonth.after(collapsedSummary)" in script
    assert '[metrics.invested, "ВЛОЖЕНО", moneySuffix()]' in script
    assert "summary-kpi-profit" in script
    assert "updateCollapsedSummaryVisibility" in script
    assert "collapsedSummary.hidden = month.open" in script
    assert "data-action=\"edit-item-field\"" in script
    assert "function metricClass" in script
    assert "item-profit-cell" in script
    assert "scrollToCatalogTop" in script
    assert "updateScrollTopButton" in script
    assert "analyticsPortfolioPickerMenu" in script
    assert "telegramPortfolioPickerMenu" in script
    assert "newItemPortfolioPickerMenu" in script
    assert 'setView("telegram")' in script
    assert 'setView("new-item")' in script
    assert 'setView("settings")' in script
    assert "rateInput.focus()" not in script
    assert "purchase_price_pln\"]').focus()" not in script
    assert "status-${item.sale_state}" in script
    assert "УШЛА НА БЛАГОЕ ДЕЛО" in script
    assert "/sale-date" in script
    assert "file-picker" in page.text
    assert "Выберите файл" not in page.text
    assert "monthOpenState" in script
    assert "Канал привязан. Новые публикации будут импортироваться автоматически." in script
    assert "telegramPollButton" not in script
    assert "refreshButton" not in client.get("/").text
    assert "Проверить сейчас" not in client.get("/").text
    assert ".scroll-top-button" in styles
    assert "background: #121314" in styles
    assert "background: #0c0d0f" in styles
    assert "grid-column: 1 / -1" in styles
    assert "grid-row: 5" in styles
    assert "inline-size: 100%" in styles
    assert "date-input-shell" in page.text
    assert ".new-item form .date-input-shell input[type=\"date\"]::-webkit-date-and-time-value" in styles
    assert "grid-template-columns: repeat(5, minmax(0, 1fr))" in styles
    assert "currency-menu-close" in styles
    assert "function closeCurrencyPanel" in script
    assert "Currency names stay connected to the compact currency surface" in styles
    assert "overflow-x: hidden" in styles
    assert ".telegram-active .page-header" in styles
    assert "z-index: 50" in styles
    assert "Desktop analytics keeps both selectors inside the heading" in styles
    assert "Добавить расход" in script
    assert "purchase_expense" in script
    assert "/api/settings/automatic-expense" in script
    assert "automaticExpensePortfolioPickerMenu" in script
    assert ".settings-panel" in styles


def test_web_fonts_are_served_with_a_font_mime_type(web_client) -> None:
    client, _app, _paths = web_client
    response = client.get("/fonts/onest/Onest%5Bwght%5D.ttf")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("font/ttf")
    assert len(response.content) > 100_000

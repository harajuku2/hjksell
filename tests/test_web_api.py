"""API coverage for the isolated local web skeleton."""

from __future__ import annotations

from datetime import date
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
    assert health.json() == {"status": "ok", "data_scope": "isolated-web-development"}
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
    assert september["metrics"]["revenue"] == "25.00"
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
    assert page.text.index('<section class="toolbar"') < page.text.index('<div class="header-actions">')
    assert 'id="collapsedSummary"' in page.text
    script = client.get("/app.js").text
    assert '<details class="month"' in script
    assert '<div class="month-body">' in script
    assert "monthly-values" in script
    assert "group.items.map(itemHtml)" in script
    assert 'data-action="menu"' in script
    assert "portfolioNameInput" in script
    assert "saleDrafts" in script
    assert "catalogIsBeingEdited" in script
    assert "telegramChannelDirty" in script
    assert "rateDirty" in script
    assert "rateInput.blur()" in script
    assert "openItemMenuId" in script
    assert "item-content" in script
    assert "collapsedSummaryHtml" in script
    assert '[metrics.invested, "ВЛОЖЕНО", " BYN"]' in script
    assert "summary-kpi-profit" in script
    assert "updateCollapsedSummaryVisibility" in script
    assert "collapsedSummary.hidden = month.open" in script
    assert "data-action=\"edit-item-field\"" in script
    assert "/sale-date" in script
    assert "file-picker" in page.text
    assert "Выберите файл" not in page.text
    assert "monthOpenState" in script
    assert "Канал привязан. Новые публикации будут импортироваться автоматически." in script
    assert "telegramPollButton" not in script
    assert "refreshButton" not in client.get("/").text
    assert "Проверить сейчас" not in client.get("/").text

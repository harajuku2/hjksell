"""Security coverage for public Telegram Mini App mode."""

from __future__ import annotations

from hashlib import sha256
import hmac
import json
from pathlib import Path
import time
from urllib.parse import urlencode

from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from hjksell.database.models import TelegramConfig
from hjksell.database.connection import initialize_database
from hjksell.repositories.portfolio_repository import PortfolioRepository
from hjksell.repositories.telegram_repository import TelegramRepository
from hjksell.web.app import create_app
from hjksell.web.config import web_dev_paths
from hjksell.web.telegram_auth import (
    authenticate_request,
    issue_session_cookie,
    validate_init_data,
    validate_session_cookie,
)


BOT_TOKEN = "123456:mini-app-test-token"


def signed_init_data(user_id: int, bot_token: str = BOT_TOKEN, auth_date: int | None = None) -> str:
    if auth_date is None:
        auth_date = int(time.time())
    values = {
        "auth_date": str(auth_date),
        "user": json.dumps({"id": user_id, "first_name": f"User {user_id}"}, separators=(",", ":")),
    }
    check_string = "\n".join(f"{key}={values[key]}" for key in sorted(values))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), sha256).digest()
    values["hash"] = hmac.new(secret_key, check_string.encode(), sha256).hexdigest()
    return urlencode(values)


def auth_header(user_id: int) -> dict[str, str]:
    return {"X-Telegram-Init-Data": signed_init_data(user_id)}


def test_init_data_signature_and_freshness_are_verified() -> None:
    valid = signed_init_data(42, auth_date=1_800_000_000)
    assert validate_init_data(valid, BOT_TOKEN, now=1_800_000_100).user_id == 42

    for invalid, now in (
        (valid.replace("hash=", "hash=0", 1), 1_800_000_100),
        (valid, 1_800_100_000),
        (valid, 1_799_999_000),
    ):
        try:
            validate_init_data(invalid, BOT_TOKEN, now=now)
        except ValueError:
            pass
        else:
            raise AssertionError("Invalid or stale Telegram initData was accepted.")


def test_init_data_rejects_duplicate_fields_and_invalid_user_ids() -> None:
    valid = signed_init_data(42, auth_date=1_800_000_000)
    invalid_payloads = (
        f"{valid}&user=%7B%22id%22%3A99%7D",
        signed_init_data(True, auth_date=1_800_000_000),
        signed_init_data(0, auth_date=1_800_000_000),
    )

    for payload in invalid_payloads:
        try:
            validate_init_data(payload, BOT_TOKEN, now=1_800_000_100)
        except ValueError:
            pass
        else:
            raise AssertionError("Malformed Telegram user data was accepted.")


def test_signed_session_cookie_is_expiring_and_tamper_evident() -> None:
    cookie = issue_session_cookie(42, BOT_TOKEN, now=1_800_000_000)
    assert validate_session_cookie(cookie, BOT_TOKEN, now=1_800_000_001) == 42
    assert validate_session_cookie(cookie, BOT_TOKEN, now=1_800_050_000) is None
    assert validate_session_cookie(cookie + "x", BOT_TOKEN, now=1_800_000_001) is None
    assert validate_session_cookie(cookie, "wrong-token", now=1_800_000_001) is None


def test_stale_init_data_falls_back_to_a_valid_session_without_refreshing_it() -> None:
    cookie = issue_session_cookie(42, BOT_TOKEN, now=1_800_000_000)
    stale_init_data = signed_init_data(99, auth_date=1_799_900_000)

    user_id, came_from_fresh_init_data = authenticate_request(
        stale_init_data,
        cookie,
        BOT_TOKEN,
        now=1_800_000_001,
    )

    assert user_id == 42
    assert came_from_fresh_init_data is False


def test_fresh_init_data_takes_precedence_over_a_different_session_cookie() -> None:
    cookie = issue_session_cookie(42, BOT_TOKEN, now=1_800_000_000)

    user_id, came_from_fresh_init_data = authenticate_request(
        signed_init_data(99, auth_date=1_800_000_001),
        cookie,
        BOT_TOKEN,
        now=1_800_000_001,
    )

    assert user_id == 99
    assert came_from_fresh_init_data is True


def test_public_mode_refuses_legacy_portfolios_without_owners(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("HJKSELL_MINI_APP_BOT_TOKEN", BOT_TOKEN)
    monkeypatch.setenv("HJKSELL_TOKEN_ENCRYPTION_KEY", Fernet.generate_key().decode("ascii"))
    paths = web_dev_paths(tmp_path / "legacy-data")
    engine, factory = initialize_database(paths)
    with factory() as session:
        PortfolioRepository(session).ensure_default_portfolios()
        session.commit()

    try:
        create_app(paths, public_mode=True)
    except RuntimeError as exc:
        assert "без Telegram-владельца" in str(exc)
    else:
        raise AssertionError("Production accepted portfolios without a verified Telegram owner.")
    finally:
        engine.dispose()


def test_public_api_is_authenticated_and_portfolios_are_tenant_scoped(
    tmp_path: Path, monkeypatch
) -> None:
    encryption_key = Fernet.generate_key().decode("ascii")
    monkeypatch.setenv("HJKSELL_MINI_APP_BOT_TOKEN", BOT_TOKEN)
    monkeypatch.setenv("HJKSELL_TOKEN_ENCRYPTION_KEY", encryption_key)
    app = create_app(web_dev_paths(tmp_path / "public-data"), public_mode=True)

    with TestClient(app, base_url="https://testserver") as client:
        assert client.get("/api/health").json()["data_deletion_enabled"] is True
        unauthenticated = client.get("/api/portfolios")
        assert unauthenticated.status_code == 401
        assert unauthenticated.headers["cache-control"] == "private, no-store"
        assert unauthenticated.headers["vary"] == "Cookie, X-Telegram-Init-Data"
        assert client.delete("/api/me/data").status_code == 401

        first_response = client.get("/api/portfolios", headers=auth_header(101))
        assert first_response.headers["cache-control"] == "private, no-store"
        first_portfolio = first_response.json()[0]
        assert first_portfolio["name"] == "Мой портфель"
        second_portfolio = client.post(
            "/api/portfolios",
            headers=auth_header(202),
            json={"name": "Мой портфель"},
        ).json()
        assert second_portfolio["id"] != first_portfolio["id"]
        assert client.get("/api/portfolios", headers=auth_header(202)).json() == [second_portfolio]

        denied = client.get(
            "/api/catalog",
            headers=auth_header(202),
            params={"portfolio_id": first_portfolio["id"]},
        )
        assert denied.status_code == 404
        assert client.put(
            "/api/settings/exchange-rate",
            headers=auth_header(202),
            json={"rate": "1.2500", "portfolio_id": first_portfolio["id"]},
        ).status_code == 404

        assert client.get("/docs").status_code == 404
        assert client.get("/openapi.json").status_code == 404

    app.state.engine.dispose()


def test_public_photos_are_scoped_to_the_item_owner(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("HJKSELL_MINI_APP_BOT_TOKEN", BOT_TOKEN)
    monkeypatch.setenv("HJKSELL_TOKEN_ENCRYPTION_KEY", Fernet.generate_key().decode("ascii"))
    app = create_app(web_dev_paths(tmp_path / "public-media"), public_mode=True)

    with TestClient(app, base_url="https://testserver") as client:
        portfolio = client.get("/api/portfolios", headers=auth_header(303)).json()[0]
        item = client.post(
            "/api/items",
            headers=auth_header(303),
            json={
                "portfolio_id": portfolio["id"],
                "purchase_price_pln": "10",
                "purchase_date": "2026-09-23",
            },
        ).json()
        uploaded = client.post(
            f"/api/items/{item['id']}/photo",
            headers={**auth_header(303), "Content-Type": "image/png"},
            params={"portfolio_id": portfolio["id"], "filename": "shoe.png"},
            content=b"\x89PNG\r\n\x1a\nfixture",
        )
        assert uploaded.status_code == 200
        assert uploaded.headers["cache-control"] == "private, no-store"
        photo_url = uploaded.json()["photo_url"]
        owned_photo = client.get(photo_url, headers=auth_header(303))
        assert owned_photo.status_code == 200
        assert owned_photo.headers["cache-control"] == "private, no-store"

        client.get("/api/portfolios", headers=auth_header(404))
        assert client.get(photo_url).status_code == 404

    app.state.engine.dispose()


def test_owner_can_delete_all_data_without_affecting_another_telegram_user(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("HJKSELL_MINI_APP_BOT_TOKEN", BOT_TOKEN)
    monkeypatch.setenv("HJKSELL_TOKEN_ENCRYPTION_KEY", Fernet.generate_key().decode("ascii"))
    app = create_app(web_dev_paths(tmp_path / "tenant-data-deletion"), public_mode=True)

    with TestClient(app, base_url="https://testserver") as client:
        owner_headers = auth_header(606)
        other_headers = auth_header(707)
        owner_portfolio = client.get("/api/portfolios", headers=owner_headers).json()[0]
        other_portfolio = client.get("/api/portfolios", headers=other_headers).json()[0]
        item = client.post(
            "/api/items",
            headers=owner_headers,
            json={
                "portfolio_id": owner_portfolio["id"],
                "purchase_price_pln": "10",
                "purchase_date": "2026-09-23",
            },
        ).json()
        uploaded = client.post(
            f"/api/items/{item['id']}/photo",
            headers={**owner_headers, "Content-Type": "image/png"},
            params={"portfolio_id": owner_portfolio["id"], "filename": "shoe.png"},
            content=b"\x89PNG\r\n\x1a\nfixture",
        )
        assert uploaded.status_code == 200
        photo_path = Path(app.state.paths.photos / Path(uploaded.json()["photo_url"].split("/")[-1].split("?")[0]))
        assert photo_path.is_file()

        deleted = client.delete("/api/me/data", headers=owner_headers)
        assert deleted.status_code == 200
        assert deleted.json()["deleted_portfolios"] == 1
        assert deleted.json()["deleted_photos"] == 1
        assert not photo_path.exists()
        assert client.get("/api/portfolios", headers=other_headers).json() == [other_portfolio]
        assert client.get(
            "/api/catalog",
            headers=other_headers,
            params={"portfolio_id": other_portfolio["id"]},
        ).json()["months"][0]["items"] == []
        recreated = client.get("/api/portfolios", headers=owner_headers).json()
        assert len(recreated) == 1
        assert recreated[0]["id"] != owner_portfolio["id"]

    app.state.engine.dispose()


def test_public_telegram_tokens_are_encrypted_in_database(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("HJKSELL_MINI_APP_BOT_TOKEN", BOT_TOKEN)
    monkeypatch.setenv("HJKSELL_TOKEN_ENCRYPTION_KEY", Fernet.generate_key().decode("ascii"))
    app = create_app(web_dev_paths(tmp_path / "encrypted-tokens"), public_mode=True)

    with TestClient(app, base_url="https://testserver") as client:
        portfolio = client.get("/api/portfolios", headers=auth_header(505)).json()[0]
        app.state.telegram_manager.reconfigure = lambda _portfolio_id: None
        saved = client.put(
            "/api/telegram/config",
            headers=auth_header(505),
            json={"portfolio_id": portfolio["id"], "token": "999:private-import-token"},
        )
        assert saved.status_code == 200
        with app.state.session_factory() as session:
            stored = session.get(TelegramConfig, portfolio["id"]).token
            assert stored is not None
            assert stored.startswith("fernet:v1:")
            assert "private-import-token" not in stored
            assert TelegramRepository(session).token(portfolio["id"]) == "999:private-import-token"

    app.state.engine.dispose()

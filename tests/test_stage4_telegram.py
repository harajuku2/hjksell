"""Fake Bot API coverage for the Stage 4 Telegram integration."""

from __future__ import annotations

import threading
import time
import logging
from datetime import datetime
from pathlib import Path

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from hjksell.config import AppPaths
from hjksell.database.models import Base, Item, TelegramImport
from hjksell.repositories.portfolio_repository import PortfolioRepository
from hjksell.repositories.telegram_repository import TelegramRepository
from hjksell.services.photos import PhotoService
from hjksell.services.telegram import (
    TelegramApiClient,
    TelegramImportService,
    TelegramWorker,
    parse_channel_post,
)


def make_factory(tmp_path: Path):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)
    with factory() as session:
        PortfolioRepository(session).ensure_default_portfolios()
        session.commit()
    paths = AppPaths(tmp_path, tmp_path / "data", tmp_path / "data" / "photos", tmp_path / "logs", tmp_path / "db", tmp_path / "app.log")
    return factory, PhotoService(paths)


def post(update_id: int = 1, channel_id: int = -1001, caption: str = "150,50") -> dict:
    return {
        "update_id": update_id,
        "channel_post": {
            "message_id": 42,
            "date": int(datetime(2026, 9, 11, 20).timestamp()),
            "chat": {"id": channel_id, "title": "Purchases", "type": "channel"},
            "photo": [{"file_id": "photo-small"}, {"file_id": "photo-large"}],
            "caption": caption,
        },
    }


@pytest.mark.parametrize("caption", ["150", "150.5", "150.50", "150,5", "150,50", " 150 , 50 "])
def test_channel_post_price_parser_accepts_documented_formats(caption: str) -> None:
    parsed = parse_channel_post(post(caption=caption))
    assert parsed.price_pln in {"150", "150.5", "150.50"}
    assert parsed.purchase_date.isoformat() == "2026-09-11"


def test_parser_rejects_albums_and_posts_without_one_photo() -> None:
    album = post()
    album["channel_post"]["media_group_id"] = "album"
    with pytest.raises(ValueError):
        parse_channel_post(album)
    no_photo = post()
    no_photo["channel_post"]["photo"] = []
    with pytest.raises(ValueError):
        parse_channel_post(no_photo)


class FakeApi:
    def __init__(self) -> None:
        self.downloads = 0
        self.fail_download = False

    def download_photo(self, file_id: str) -> tuple[bytes, str]:
        self.downloads += 1
        if self.fail_download:
            raise RuntimeError("network unavailable")
        return b"fake image", ".jpg"

    def get_updates(self, offset=None, timeout=50):
        return []


def test_import_is_atomic_snapshotted_and_duplicate_safe(tmp_path: Path) -> None:
    factory, photos = make_factory(tmp_path)
    api = FakeApi()
    importer = TelegramImportService(factory, photos, api)
    with factory() as session:
        channel = TelegramRepository(session).bind_channel(1, "-1001", "Purchases")
        session.commit()
    first = importer.import_update(post())
    duplicate_message = importer.import_update(post(update_id=2))
    assert first.status == "imported"
    assert duplicate_message.status == "duplicate"
    assert api.downloads == 1
    with factory() as session:
        item = session.query(Item).one()
        assert item.purchase_price_pln == 150.50
        assert item.purchase_date.isoformat() == "2026-09-11"
        assert item.telegram_channel_id == "-1001"
        assert TelegramRepository(session).offset() == 3
        assert Path(item.photo_path).is_file()


def test_unknown_channel_is_ignored_and_offset_persisted(tmp_path: Path) -> None:
    factory, photos = make_factory(tmp_path)
    importer = TelegramImportService(factory, photos, FakeApi())
    result = importer.import_update(post(channel_id=-999))
    assert result.status == "ignored"
    with factory() as session:
        assert session.query(Item).count() == 0
        assert TelegramRepository(session).offset() == 2
        diagnostic = session.query(TelegramImport).one()
        assert diagnostic.status == "ignored"
        discovered = TelegramRepository(session).discovered_channels()
        assert [(channel.channel_id, channel.title) for channel in discovered] == [("-999", "Purchases")]


def test_telegram_transport_loggers_are_disabled() -> None:
    TelegramApiClient("123:secret", client=httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, json={"ok": True, "result": []}))))
    assert logging.getLogger("httpx").disabled
    assert logging.getLogger("httpcore").disabled


def test_saved_token_is_restored_after_application_restart(tmp_path: Path) -> None:
    factory, _photos = make_factory(tmp_path)
    fake_token = "123456:fake-token"

    with factory() as session:
        TelegramRepository(session).set_token(fake_token)
        session.commit()

    # A new session represents the next application process.
    with factory() as restarted_session:
        assert TelegramRepository(restarted_session).token() == fake_token


def test_download_error_is_retryable_without_advancing_offset(tmp_path: Path) -> None:
    factory, photos = make_factory(tmp_path)
    api = FakeApi()
    api.fail_download = True
    importer = TelegramImportService(factory, photos, api)
    with factory() as session:
        TelegramRepository(session).bind_channel(1, "-1001")
        session.commit()
    assert importer.import_update(post()).status == "error"
    with factory() as session:
        assert TelegramRepository(session).offset() is None
        assert session.query(TelegramImport).one().status == "error"
    api.fail_download = False
    assert importer.import_update(post()).status == "imported"


def test_bot_api_uses_get_me_and_get_updates_without_send_methods() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path.endswith("/getMe"):
            return httpx.Response(200, json={"ok": True, "result": {"username": "hjk_bot"}})
        return httpx.Response(200, json={"ok": True, "result": []})

    client = TelegramApiClient("123:secret", client=httpx.Client(transport=httpx.MockTransport(handler)))
    assert client.get_me()["username"] == "hjk_bot"
    assert client.get_updates(offset=9) == []
    assert [request.url.path.split("/")[-1] for request in requests] == ["getMe", "getUpdates"]
    assert "sendMessage" not in dir(client)


def test_poll_worker_prevents_overlapping_requests() -> None:
    class SlowImporter:
        def poll_once(self):
            time.sleep(0.05)
            return ["done"]

    worker = TelegramWorker(SlowImporter(), interval_seconds=1)
    results: list[list] = []
    first = threading.Thread(target=lambda: results.append(worker.poll_once()))
    first.start()
    time.sleep(0.005)
    assert worker.poll_once() == []
    first.join()
    assert results == [["done"]]

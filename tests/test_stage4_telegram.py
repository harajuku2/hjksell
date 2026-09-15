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
from PySide6.QtCore import QObject, QThread, Signal, Slot
from PySide6.QtWidgets import QApplication

from hjksell.config import AppPaths
from hjksell.database.models import Base, Item, TelegramConfig, TelegramImport
from hjksell.repositories.portfolio_repository import PortfolioRepository
from hjksell.repositories.telegram_repository import TelegramRepository
from hjksell.services.photos import PhotoService
from hjksell.services.telegram import (
    TelegramApiClient,
    TelegramApiError,
    TelegramImportService,
    TelegramQtWorker,
    TelegramWorker,
    parse_channel_post,
)
from hjksell.ui.main_window import TelegramSettingsDialog


def make_factory(tmp_path: Path):
    engine = create_engine(
        f"sqlite:///{(tmp_path / 'test.db').as_posix()}",
        connect_args={"check_same_thread": False},
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


def test_channel_post_price_parser_accepts_free_item_price() -> None:
    parsed = parse_channel_post(post(caption="0"))
    assert parsed.price_pln == "0"


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


class QueueApi(FakeApi):
    def __init__(self, updates: list[dict]) -> None:
        super().__init__()
        self.updates = updates
        self.offsets: list[int | None] = []

    def get_updates(self, offset=None, timeout=50):
        self.offsets.append(offset)
        updates, self.updates = self.updates, []
        return updates


class BlockingApi(FakeApi):
    def __init__(self) -> None:
        super().__init__()
        self.started = threading.Event()
        self.closed = threading.Event()

    def get_updates(self, offset=None, timeout=50):
        self.started.set()
        self.closed.wait(2)
        if not self.closed.is_set():
            raise RuntimeError("blocking fake did not stop")
        raise RuntimeError("closed")

    def close(self) -> None:
        self.closed.set()


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


def test_telegram_import_creates_free_item(tmp_path: Path) -> None:
    factory, photos = make_factory(tmp_path)
    api = FakeApi()
    importer = TelegramImportService(factory, photos, api)
    with factory() as session:
        TelegramRepository(session).bind_channel(1, "-1001", "Purchases")
        session.commit()

    result = importer.import_update(post(caption="0"))
    assert result.status == "imported"
    with factory() as session:
        item = session.query(Item).one()
        assert item.purchase_price_pln == 0
        assert item.cost_byn == 0


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


def test_telegram_tokens_and_offsets_are_portfolio_specific(tmp_path: Path) -> None:
    factory, _photos = make_factory(tmp_path)
    with factory() as session:
        mine, friend = PortfolioRepository(session).ensure_default_portfolios()
        repository = TelegramRepository(session)
        repository.set_token(mine.id, "111:mine")
        repository.set_token(friend.id, "222:friend")
        repository.set_offset(mine.id, 11)
        repository.set_offset(friend.id, 22)
        repository.bind_channel(mine.id, "-1001", "Mine")
        repository.bind_channel(friend.id, "-1002", "Friend")
        session.commit()

    with factory() as session:
        repository = TelegramRepository(session)
        assert repository.token(mine.id) == "111:mine"
        assert repository.token(friend.id) == "222:friend"
        assert repository.offset(mine.id) == 11
        assert repository.offset(friend.id) == 22
        assert repository.channel("-1001", mine.id).portfolio_id == mine.id
        assert repository.channel("-1002", friend.id).portfolio_id == friend.id


def test_two_portfolio_importers_keep_duplicates_and_state_independent(tmp_path: Path) -> None:
    factory, photos = make_factory(tmp_path)
    mine_api = QueueApi([post(update_id=10, channel_id=-1001)])
    friend_api = QueueApi([post(update_id=10, channel_id=-1002)])
    with factory() as session:
        mine, friend = PortfolioRepository(session).ensure_default_portfolios()
        repository = TelegramRepository(session)
        repository.set_token(mine.id, "111:mine")
        repository.set_token(friend.id, "222:friend")
        repository.bind_channel(mine.id, "-1001")
        repository.bind_channel(friend.id, "-1002")
        session.commit()

    mine_importer = TelegramImportService(factory, photos, mine_api, mine.id)
    friend_importer = TelegramImportService(factory, photos, friend_api, friend.id)
    assert mine_importer.poll_once()[0].status == "imported"
    assert friend_importer.poll_once()[0].status == "imported"
    assert mine_api.offsets == [None]
    assert friend_api.offsets == [None]

    with factory() as session:
        mine, friend = PortfolioRepository(session).ensure_default_portfolios()
        items = session.query(Item).order_by(Item.portfolio_id).all()
        assert [item.portfolio_id for item in items] == [mine.id, friend.id]
        repository = TelegramRepository(session)
        assert repository.offset(mine.id) == 11
        assert repository.offset(friend.id) == 11
        assert session.query(TelegramImport).count() == 2
        assert session.query(TelegramConfig).count() == 2


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


def test_bot_api_explains_http_conflicts_without_exposing_token() -> None:
    client = TelegramApiClient(
        "123:secret",
        client=httpx.Client(
            transport=httpx.MockTransport(lambda request: httpx.Response(409, json={"ok": False}))
        ),
    )
    with pytest.raises(TelegramApiError) as error:
        client.get_updates()
    assert "другим polling-процессом" in str(error.value)
    assert "secret" not in str(error.value)


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


def test_polling_worker_stops_blocking_long_poll_cooperatively(tmp_path: Path) -> None:
    factory, photos = make_factory(tmp_path)
    api = BlockingApi()
    with factory() as session:
        TelegramRepository(session).set_token(1, "111:fake")
        session.commit()
    importer = TelegramImportService(factory, photos, api, portfolio_id=1)
    worker = TelegramWorker(importer, interval_seconds=1)
    thread = threading.Thread(target=worker.run)
    thread.start()
    assert api.started.wait(1)

    worker.stop()
    thread.join(1)

    assert not thread.is_alive()
    assert api.closed.is_set()


def test_two_polling_workers_stop_independently(tmp_path: Path) -> None:
    factory, photos = make_factory(tmp_path)
    first_api = BlockingApi()
    second_api = BlockingApi()
    with factory() as session:
        TelegramRepository(session).set_token(1, "111:fake")
        TelegramRepository(session).set_token(2, "222:fake")
        session.commit()
    first = TelegramWorker(TelegramImportService(factory, photos, first_api, 1), interval_seconds=1)
    second = TelegramWorker(TelegramImportService(factory, photos, second_api, 2), interval_seconds=1)
    first_thread = threading.Thread(target=first.run)
    second_thread = threading.Thread(target=second.run)
    first_thread.start()
    second_thread.start()
    assert first_api.started.wait(1)
    assert second_api.started.wait(1)

    first.stop()
    first_thread.join(1)
    assert not first_thread.is_alive()
    assert second_thread.is_alive()

    second.stop()
    second_thread.join(1)
    assert not second_thread.is_alive()


def test_telegram_diagnostics_are_queued_to_gui_thread() -> None:
    app = QApplication.instance() or QApplication([])

    class FakeImporter:
        portfolio_id = 2

    class TestWorker(TelegramQtWorker):
        trigger = Signal(object)

    class Receiver(QObject):
        def __init__(self) -> None:
            super().__init__()
            self.thread_id: int | None = None
            self.portfolio_id: int | None = None

        @Slot(int, object)
        def receive(self, portfolio_id: int, _values: object) -> None:
            self.thread_id = threading.get_ident()
            self.portfolio_id = portfolio_id

    worker = TestWorker(FakeImporter())
    thread = QThread()
    receiver = Receiver()
    worker.moveToThread(thread)
    worker.diagnostics.connect(receiver.receive)
    worker.trigger.connect(worker._emit_diagnostics)
    thread.start()
    assert thread.isRunning()
    worker.trigger.emit([])
    deadline = time.monotonic() + 1
    while receiver.thread_id is None and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.01)
    thread.quit()
    thread.wait(1000)

    assert receiver.portfolio_id == 2
    assert receiver.thread_id == threading.get_ident()
    assert not thread.isRunning()




def test_telegram_settings_waits_for_validation_thread_before_close() -> None:
    app = QApplication.instance() or QApplication([])
    dialog = TelegramSettingsDialog([], None, None)
    thread = QThread(dialog)
    thread.start()
    assert thread.isRunning()
    dialog._validation_thread = thread
    dialog._validation_worker = object()

    dialog._validation_finished(True, "Проверка пройдена.")

    assert not thread.isRunning()
    assert dialog._validation_thread is None
    assert dialog._validation_worker is None
    dialog.deleteLater()

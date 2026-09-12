"""Non-UI behaviour introduced by the stage-three catalogue."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from hjksell.config import AppPaths
from hjksell.database.models import Base, ItemStatus
from hjksell.repositories.item_repository import ItemRepository
from hjksell.repositories.portfolio_repository import PortfolioRepository
from hjksell.repositories.settings_repository import SettingsRepository
from hjksell.services.items import ItemService
from hjksell.services.photos import PhotoService


def make_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)


def test_current_rate_is_persisted_and_new_items_keep_historical_rate() -> None:
    with make_session() as session:
        mine, _ = PortfolioRepository(session).ensure_default_portfolios()
        settings = SettingsRepository(session)
        settings.set_exchange_rate(Decimal("0.8700"))
        service = ItemService(ItemRepository(session), settings)
        item = service.create_from_text(mine.id, "150,50", date(2026, 9, 11))
        session.commit()
        assert item.exchange_rate == Decimal("0.8700")
        assert item.cost_byn == Decimal("130.94")
        assert SettingsRepository(session).current_exchange_rate() == Decimal("0.8700")


def test_changing_current_rate_does_not_recalculate_existing_item() -> None:
    with make_session() as session:
        mine, _ = PortfolioRepository(session).ensure_default_portfolios()
        settings = SettingsRepository(session)
        service = ItemService(ItemRepository(session), settings)
        item = service.create_from_text(mine.id, "100", date(2026, 9, 1))
        original_cost = item.cost_byn
        settings.set_exchange_rate(Decimal("0.9000"))
        session.commit()
        assert item.exchange_rate == Decimal("0.8500")
        assert item.cost_byn == original_cost == Decimal("85.00")


def test_new_items_are_ordered_by_purchase_date_and_creation_id() -> None:
    with make_session() as session:
        mine, _ = PortfolioRepository(session).ensure_default_portfolios()
        settings = SettingsRepository(session)
        service = ItemService(ItemRepository(session), settings)
        older = service.create_from_text(mine.id, "100", date(2026, 8, 1))
        newest_date = service.create_from_text(mine.id, "120", date(2026, 9, 1))
        same_day_newer = service.create_from_text(mine.id, "130", date(2026, 9, 1))
        session.commit()
        items = ItemRepository(session).active_items(mine.id)
        assert [item.id for item in items] == [same_day_newer.id, newest_date.id, older.id]


def test_sale_validation_and_repository_status() -> None:
    with make_session() as session:
        mine, _ = PortfolioRepository(session).ensure_default_portfolios()
        settings = SettingsRepository(session)
        service = ItemService(ItemRepository(session), settings)
        item = service.create_from_text(mine.id, "100", date(2026, 9, 1))
        try:
            service.sell(item, "0")
        except ValueError:
            pass
        else:
            raise AssertionError("zero sale price must be rejected")
        service.sell(item, "200,5", date(2026, 9, 12))
        assert item.status == ItemStatus.SOLD.value
        assert item.sale_price_byn == Decimal("200.50")


def test_photo_service_copies_to_data_photos(tmp_path) -> None:
    paths = AppPaths(tmp_path / "root", tmp_path / "data", tmp_path / "data" / "photos", tmp_path / "logs", tmp_path / "db.sqlite", tmp_path / "logs" / "app.log")
    source = tmp_path / "source.png"
    source.write_bytes(b"not decoded by the copy operation")
    copied = Path(PhotoService(paths).copy_photo(source))
    assert copied.parent == paths.photos
    assert copied.read_bytes() == source.read_bytes()

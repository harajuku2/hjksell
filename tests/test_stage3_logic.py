"""Non-UI behaviour introduced by the stage-three catalogue."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QColor, QImage, QPainter
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from hjksell.app import build_stylesheet
from hjksell.config import AppPaths
from hjksell.database.models import Base, ItemStatus
from hjksell.repositories.item_repository import ItemRepository
from hjksell.repositories.portfolio_repository import PortfolioRepository
from hjksell.repositories.settings_repository import SettingsRepository
from hjksell.repositories.telegram_repository import TelegramRepository
from hjksell.services.items import ItemService
from hjksell.services.photos import PhotoService
from hjksell.services.finance import item_metrics
from hjksell.services.portfolios import PortfolioService
from hjksell.ui.main_window import MainWindow, QFrameCard, catalog_metric_tone, item_matches_catalog_filter
from hjksell.ui.neon_widgets import CatalogBackdrop, PhotoSurface
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QApplication, QLabel, QWidget


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
        service.sell(item, "0", date(2026, 9, 12))
        assert item.status == ItemStatus.SOLD.value
        assert item.sale_price_byn == Decimal("0.00")
        assert item.sale_date == date(2026, 9, 12)
        service.sell(item, "200,5", date(2026, 9, 12))
        assert item.status == ItemStatus.SOLD.value
        assert item.sale_price_byn == Decimal("200.50")


def test_free_item_is_valid_and_has_undefined_efficiency_metrics() -> None:
    with make_session() as session:
        mine, _ = PortfolioRepository(session).ensure_default_portfolios()
        service = ItemService(ItemRepository(session), SettingsRepository(session))
        item = service.create_from_text(mine.id, "0", date(2026, 9, 1))
        assert item.purchase_price_pln == Decimal("0.00")
        assert item.cost_byn == Decimal("0.00")
        unsold_metrics = item_metrics(None, item.cost_byn)
        assert unsold_metrics.profit is None
        assert unsold_metrics.x is None
        assert unsold_metrics.roi is None
        service.sell(item, "100", date(2026, 9, 12))
        metrics = item_metrics(item.sale_price_byn, item.cost_byn)
        assert metrics.profit == Decimal("100.00")
        assert metrics.x is None
        assert metrics.roi is None
        service.sell(item, "0", date(2026, 9, 13))
        metrics = item_metrics(item.sale_price_byn, item.cost_byn)
        assert metrics.profit == Decimal("0.00")
        assert metrics.x is None
        assert metrics.roi is None


def test_negative_purchase_price_is_rejected() -> None:
    with make_session() as session:
        mine, _ = PortfolioRepository(session).ensure_default_portfolios()
        service = ItemService(ItemRepository(session), SettingsRepository(session))
        with pytest.raises(ValueError):
            service.create_from_text(mine.id, "-1", date(2026, 9, 1))


def test_sale_can_be_cancelled_and_sold_again_with_new_date() -> None:
    with make_session() as session:
        mine, _ = PortfolioRepository(session).ensure_default_portfolios()
        settings = SettingsRepository(session)
        service = ItemService(ItemRepository(session), settings)
        item = service.create_from_text(mine.id, "100", date(2026, 9, 1))
        service.sell(item, "200", date(2026, 9, 12))
        service.sell(item, "")
        assert item.status == ItemStatus.IN_STOCK.value
        assert item.sale_price_byn is None
        assert item.sale_date is None
        service.sell(item, "250", date(2026, 9, 20))
        assert item.status == ItemStatus.SOLD.value
        assert item.sale_price_byn == Decimal("250.00")
        assert item.sale_date == date(2026, 9, 20)


def test_negative_sale_price_is_rejected() -> None:
    with make_session() as session:
        mine, _ = PortfolioRepository(session).ensure_default_portfolios()
        service = ItemService(ItemRepository(session), SettingsRepository(session))
        item = service.create_from_text(mine.id, "100", date(2026, 9, 1))
        try:
            service.sell(item, "-1")
        except ValueError:
            pass
        else:
            raise AssertionError("negative sale price must be rejected")


def test_catalog_filters_distinguish_stock_positive_and_zero_sale() -> None:
    with make_session() as session:
        mine, _ = PortfolioRepository(session).ensure_default_portfolios()
        service = ItemService(ItemRepository(session), SettingsRepository(session))
        stock = service.create_from_text(mine.id, "100", date(2026, 9, 1))
        positive = service.create_from_text(mine.id, "110", date(2026, 9, 2))
        zero = service.create_from_text(mine.id, "120", date(2026, 9, 3))
        service.sell(positive, "200", date(2026, 9, 10))
        service.sell(zero, "0", date(2026, 9, 11))

        assert item_matches_catalog_filter(stock, "stock")
        assert not item_matches_catalog_filter(stock, "sold")
        assert not item_matches_catalog_filter(stock, "no_revenue")
        assert item_matches_catalog_filter(positive, "sold")
        assert not item_matches_catalog_filter(positive, "stock")
        assert not item_matches_catalog_filter(positive, "no_revenue")
        assert item_matches_catalog_filter(zero, "no_revenue")
        assert not item_matches_catalog_filter(zero, "stock")
        assert not item_matches_catalog_filter(zero, "sold")


def test_catalog_metric_tones_cover_positive_negative_neutral_and_unavailable() -> None:
    assert catalog_metric_tone(Decimal("68"), Decimal("0")) == "positive"
    assert catalog_metric_tone(Decimal("-15"), Decimal("0")) == "negative"
    assert catalog_metric_tone(Decimal("0"), Decimal("0")) == "neutral"
    assert catalog_metric_tone(None, Decimal("0")) == "neutral"

    assert catalog_metric_tone(Decimal("2"), Decimal("1")) == "positive"
    assert catalog_metric_tone(Decimal("0"), Decimal("1")) == "negative"
    assert catalog_metric_tone(Decimal("1"), Decimal("1")) == "neutral"


def test_catalog_metric_tone_qss_updates_actual_foreground_color() -> None:
    app = QApplication.instance() or QApplication([])
    previous_stylesheet = app.styleSheet()
    app.setStyleSheet(build_stylesheet("Onest"))
    root = QWidget()
    root.setObjectName("catalogRoot")
    colors = {
        "positive": (118, 198, 154),
        "negative": (217, 130, 130),
        "neutral": (244, 247, 251),
    }
    try:
        for tone, expected in colors.items():
            label = QLabel("+68.00 BYN", root)
            label.setObjectName("catalogMetricValue")
            label.setProperty("tone", tone)
            style = label.style()
            style.unpolish(label)
            style.polish(label)
            actual = label.palette().color(label.foregroundRole())
            assert (actual.red(), actual.green(), actual.blue()) == expected
            assert label.property("tone") == tone
    finally:
        root.deleteLater()
        app.setStyleSheet(previous_stylesheet)
        app.processEvents()


def test_catalog_cost_value_renders_violet() -> None:
    app = QApplication.instance() or QApplication([])
    previous_stylesheet = app.styleSheet()
    app.setStyleSheet(build_stylesheet("Onest"))
    root = QWidget()
    root.setObjectName("catalogRoot")
    value = QLabel("0.85 BYN", root)
    value.setObjectName("catalogCostValue")
    value.resize(120, 30)
    root.show()
    app.processEvents()
    try:
        image = QImage(value.size(), QImage.Format.Format_ARGB32)
        image.fill(QColor("#09090b"))
        painter = QPainter(image)
        value.render(painter, QPoint(0, 0))
        painter.end()
        colors = {}
        for y in range(image.height()):
            for x in range(image.width()):
                rgb = image.pixelColor(x, y).getRgb()[:3]
                if rgb not in {(9, 9, 11), (14, 17, 23)}:
                    colors[rgb] = colors.get(rgb, 0) + 1
        assert max(colors, key=colors.get) == (201, 166, 238)
    finally:
        root.deleteLater()
        app.setStyleSheet(previous_stylesheet)
        app.processEvents()


def test_catalog_main_window_renders_metric_tones_in_item_rows() -> None:
    app = QApplication.instance() or QApplication([])
    previous_stylesheet = app.styleSheet()
    app.setStyleSheet(build_stylesheet("Onest"))
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        for directory in ("data", "photos", "logs"):
            (root / directory).mkdir()
        paths = AppPaths(
            root=root,
            data=root / "data",
            photos=root / "photos",
            logs=root / "logs",
            database=root / "data" / "hjk_sell.db",
            log_file=root / "logs" / "app.log",
        )
        engine = create_engine(f"sqlite:///{paths.database}")
        Base.metadata.create_all(engine)
        factory = sessionmaker(bind=engine, expire_on_commit=False)
        with Session(engine, expire_on_commit=False) as session:
            portfolio, _ = PortfolioRepository(session).ensure_default_portfolios()
            service = ItemService(ItemRepository(session), SettingsRepository(session))
            profitable = service.create_from_text(portfolio.id, "100", date(2026, 9, 1))
            service.sell(profitable, "500", date(2026, 9, 10))
            loss = service.create_from_text(portfolio.id, "100", date(2026, 9, 2))
            service.sell(loss, "10", date(2026, 9, 10))
            session.commit()
        window = MainWindow(session_factory=factory, paths=paths)
        window.show()
        app.processEvents()
        try:
            rendered = {}
            for object_name in ("catalogMetricValue", "catalogPrimaryMetricValue"):
                for label in window.findChildren(QLabel, object_name):
                    if label.text() in {"+415.00 BYN", "-75.00 BYN"}:
                        image = QImage(label.size(), QImage.Format.Format_ARGB32)
                        image.fill(QColor("#09090b"))
                        painter = QPainter(image)
                        label.render(painter, QPoint(0, 0))
                        painter.end()
                        colors = {}
                        for y in range(image.height()):
                            for x in range(image.width()):
                                color = image.pixelColor(x, y)
                                rgb = (color.red(), color.green(), color.blue())
                                if rgb not in {(9, 9, 11), (14, 17, 23)}:
                                    colors[rgb] = colors.get(rgb, 0) + 1
                        rendered[label.text()] = max(colors, key=colors.get)
            assert rendered == {
                "+415.00 BYN": (118, 198, 154),
                "-75.00 BYN": (217, 130, 130),
            }
        finally:
            window.close()
            app.processEvents()
            engine.dispose()
            app.setStyleSheet(previous_stylesheet)


def test_zero_sale_financial_tones_are_negative_while_status_stays_no_revenue() -> None:
    with make_session() as session:
        mine, _ = PortfolioRepository(session).ensure_default_portfolios()
        service = ItemService(ItemRepository(session), SettingsRepository(session))
        item = service.create_from_text(mine.id, "100", date(2026, 9, 1))
        service.sell(item, "0", date(2026, 9, 12))
        metrics = item_metrics(item.sale_price_byn, item.cost_byn)

        assert item.sale_price_byn == Decimal("0.00")
        assert item.status == ItemStatus.SOLD.value
        assert catalog_metric_tone(metrics.profit, Decimal("0")) == "negative"
        assert catalog_metric_tone(metrics.x, Decimal("1")) == "negative"
        assert catalog_metric_tone(metrics.roi, Decimal("0")) == "negative"


def test_cancelled_sale_returns_catalog_metrics_to_neutral_unavailable() -> None:
    with make_session() as session:
        mine, _ = PortfolioRepository(session).ensure_default_portfolios()
        service = ItemService(ItemRepository(session), SettingsRepository(session))
        item = service.create_from_text(mine.id, "100", date(2026, 9, 1))
        service.sell(item, "200", date(2026, 9, 12))
        service.sell(item, "")
        metrics = item_metrics(item.sale_price_byn, item.cost_byn)

        assert catalog_metric_tone(metrics.profit, Decimal("0")) == "neutral"
        assert catalog_metric_tone(metrics.x, Decimal("1")) == "neutral"
        assert catalog_metric_tone(metrics.roi, Decimal("0")) == "neutral"


def test_portfolio_display_names_persist_without_changing_identity_or_bindings() -> None:
    with make_session() as session:
        mine, friend = PortfolioRepository(session).ensure_default_portfolios()
        mine_id, friend_id = mine.id, friend.id
        service = PortfolioService(PortfolioRepository(session))
        service.rename(mine, "  HJK  ")
        service.rename(friend, "ПАРТНЁР")
        telegram = TelegramRepository(session)
        telegram.set_token(mine_id, "111111:mine")
        telegram.set_token(friend_id, "222222:friend")
        telegram.set_offset(mine_id, 14)
        telegram.bind_channel(mine_id, "-1001", "Mine")
        session.commit()

        reloaded = PortfolioRepository(session)
        portfolios = reloaded.list_all()
        assert [(portfolio.id, portfolio.name) for portfolio in portfolios] == [
            (mine_id, "HJK"),
            (friend_id, "ПАРТНЁР"),
        ]
        assert reloaded.ensure_default_portfolios()[0].id == mine_id
        assert reloaded.ensure_default_portfolios()[1].id == friend_id
        assert telegram.token(mine_id) == "111111:mine"
        assert telegram.token(friend_id) == "222222:friend"
        assert telegram.offset(mine_id) == 14
        assert telegram.channel("-1001", mine_id).portfolio_id == mine_id


def test_portfolio_display_name_validation_preserves_existing_name() -> None:
    with make_session() as session:
        mine, _ = PortfolioRepository(session).ensure_default_portfolios()
        service = PortfolioService(PortfolioRepository(session))
        for invalid in ("   ", "x" * 25):
            try:
                service.rename(mine, invalid)
            except ValueError:
                pass
            else:
                raise AssertionError("invalid display name must be rejected")
            assert mine.name == "МОЯ"


def test_main_window_reloads_portfolio_tabs_without_invalid_qt_api(tmp_path, monkeypatch) -> None:
    app = QApplication.instance() or QApplication([])
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)
    with factory() as session:
        PortfolioRepository(session).ensure_default_portfolios()
        session.commit()
    paths = AppPaths(
        tmp_path / "root",
        tmp_path / "data",
        tmp_path / "data" / "photos",
        tmp_path / "logs",
        tmp_path / "db.sqlite",
        tmp_path / "logs" / "app.log",
    )
    monkeypatch.setattr(MainWindow, "_start_telegram_polling", lambda self: None)
    window = MainWindow(session_factory=factory, paths=paths)
    try:
        assert [window.portfolio_tabs.tabText(index) for index in range(window.portfolio_tabs.count())] == ["МОЯ", "ДРУГА"]
        window.current_portfolio_id = 2
        with factory() as session:
            portfolio = PortfolioRepository(session).get(2)
            PortfolioService(PortfolioRepository(session)).rename(portfolio, "PARTNER")
            session.commit()
        window._load_portfolios()
        assert window.current_portfolio_id == 2
        assert [window.portfolio_tabs.tabText(index) for index in range(window.portfolio_tabs.count())] == ["МОЯ", "PARTNER"]
    finally:
        window.close()
        app.processEvents()


def test_catalog_interaction_surfaces_use_state_without_rectangular_effects(tmp_path, monkeypatch) -> None:
    app = QApplication.instance() or QApplication([])
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)
    with factory() as session:
        PortfolioRepository(session).ensure_default_portfolios()
        session.commit()
    paths = AppPaths(
        tmp_path / "root",
        tmp_path / "data",
        tmp_path / "data" / "photos",
        tmp_path / "logs",
        tmp_path / "db.sqlite",
        tmp_path / "logs" / "app.log",
    )
    monkeypatch.setattr(MainWindow, "_start_telegram_polling", lambda self: None)
    window = MainWindow(session_factory=factory, paths=paths)
    try:
        window._portfolio_changed(1)
        assert window.portfolio_tabs.graphicsEffect() is None
        assert window.portfolio_tabs.property("active") is True

        window._set_filter("all")
        active_filter = window.filter_buttons["all"]
        inactive_filter = window.filter_buttons["stock"]
        assert active_filter.graphicsEffect() is None
        assert inactive_filter.graphicsEffect() is None
        assert active_filter.isChecked()
        assert not inactive_filter.isChecked()

        window._set_filter("stock")
        assert active_filter.graphicsEffect() is None
        assert inactive_filter.graphicsEffect() is None
        assert not active_filter.isChecked()
        assert inactive_filter.isChecked()
    finally:
        window.close()
        app.processEvents()


def test_catalog_v2_surface_contract(tmp_path, monkeypatch) -> None:
    app = QApplication.instance() or QApplication([])
    previous_stylesheet = app.styleSheet()
    app.setStyleSheet(build_stylesheet("Onest"))
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)
    with factory() as session:
        PortfolioRepository(session).ensure_default_portfolios()
        session.commit()
    paths = AppPaths(
        tmp_path / "root",
        tmp_path / "data",
        tmp_path / "data" / "photos",
        tmp_path / "logs",
        tmp_path / "db.sqlite",
        tmp_path / "logs" / "app.log",
    )
    monkeypatch.setattr(MainWindow, "_start_telegram_polling", lambda self: None)
    window = MainWindow(session_factory=factory, paths=paths)
    card = QFrameCard()
    photo = PhotoSurface()
    try:
        assert isinstance(window.centralWidget(), CatalogBackdrop)
        assert window.scroll.objectName() == "catalogWorkspace"
        assert window.catalogue.objectName() == "catalogueSurface"
        assert "QScrollBar::handle:vertical" in app.styleSheet()
        assert "QToolButton#itemMenu::menu-indicator" in app.styleSheet()
        assert "QFrame#catalogItemDivider" not in app.styleSheet()
        assert window.portfolio_tabs.graphicsEffect() is None
        assert all(button.graphicsEffect() is None for button in window.filter_buttons.values())
        assert card.objectName() == "itemCard"
        card.resize(1000, 220)
        card.set_island_width(620)
        assert card._island_width == 620
        assert card._island_width < card.width()
        assert photo.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    finally:
        window.close()
        card.deleteLater()
        photo.deleteLater()
        app.processEvents()
        app.setStyleSheet(previous_stylesheet)


def test_sale_price_can_be_edited_without_changing_sale_date() -> None:
    with make_session() as session:
        mine, _ = PortfolioRepository(session).ensure_default_portfolios()
        settings = SettingsRepository(session)
        service = ItemService(ItemRepository(session), settings)
        item = service.create_from_text(mine.id, "100", date(2026, 9, 1))
        service.sell(item, "300", date(2026, 9, 12))
        first_sale_date = item.sale_date
        service.sell(item, "350", date(2026, 9, 20))
        metrics = item_metrics(item.sale_price_byn, item.cost_byn)
        assert item.sale_price_byn == Decimal("350.00")
        assert item.sale_date == first_sale_date == date(2026, 9, 12)
        assert metrics.profit == Decimal("265.00")
        assert metrics.x == Decimal("4.12")
        assert metrics.roi == Decimal("311.76")


def test_photo_service_copies_to_data_photos(tmp_path) -> None:
    paths = AppPaths(tmp_path / "root", tmp_path / "data", tmp_path / "data" / "photos", tmp_path / "logs", tmp_path / "db.sqlite", tmp_path / "logs" / "app.log")
    source = tmp_path / "source.png"
    source.write_bytes(b"not decoded by the copy operation")
    copied = Path(PhotoService(paths).copy_photo(source))
    assert copied.parent == paths.photos
    assert copied.read_bytes() == source.read_bytes()


def test_item_menu_actions_ignore_qt_checked_argument() -> None:
    app = QApplication.instance() or QApplication([])
    item = object()
    received: list[object] = []
    action = QAction("Удалить")
    action.triggered.connect(lambda _checked=False, current=item: received.append(current))

    action.trigger()

    assert received == [item]


def test_item_metric_blocks_put_values_above_labels() -> None:
    app = QApplication.instance() or QApplication([])
    block = MainWindow._metric_block("+68.00 BYN", "ПРИБЫЛЬ", value_object_name="profitValue")
    try:
        layout = block.layout()
        assert layout is not None
        assert layout.spacing() == 4
        assert block.sizePolicy().verticalPolicy().name == "Fixed"
        assert layout.itemAt(0).widget().text() == "+68.00 BYN"
        assert layout.itemAt(0).widget().objectName() == "profitValue"
        assert layout.itemAt(1).widget().text() == "ПРИБЫЛЬ"
    finally:
        block.deleteLater()
        app.processEvents()

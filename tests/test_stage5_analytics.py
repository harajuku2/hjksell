"""Stage-five detailed analytics coverage."""

from datetime import date
from decimal import Decimal
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from hjksell.app import build_stylesheet
from hjksell.database.models import Base, Item, ItemStatus
from hjksell.repositories.item_repository import ItemRepository
from hjksell.repositories.portfolio_repository import PortfolioRepository
from hjksell.services.analytics import AnalyticsPeriod, AnalyticsService, PeriodPreset
from hjksell.ui.analytics_window import AnalyticsWindow
from hjksell.ui.typography import Typography, TypographyRole, load_typography
from hjksell.ui.main_window import MainWindow
from PySide6.QtGui import QFont, QFontDatabase, QFontMetrics, QRawFont
from PySide6.QtWidgets import QApplication, QLabel, QLineEdit, QWidget


def make_session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)


def item(session, portfolio_id, purchase, *, cost="85.00", sale=None, sold=None):
    return ItemRepository(session).add_item(Item(
        portfolio_id=portfolio_id,
        purchase_date=purchase,
        purchase_price_pln=Decimal(cost),
        exchange_rate=Decimal("1.0000"),
        cost_byn=Decimal(cost),
        status=ItemStatus.SOLD.value if sale is not None else ItemStatus.IN_STOCK.value,
        sale_price_byn=None if sale is None else Decimal(sale),
        sale_date=sold,
    ))


def test_typography_registers_supplied_and_official_font_families() -> None:
    app = QApplication.instance() or QApplication([])
    typography = load_typography(lambda relative: Path(relative))

    assert typography.kulag_sha == "KULAG SHA"
    assert typography.kulag_sha_style == "Regular"
    assert typography.kulag_sha_outline
    assert typography.kulag_sha_outline_style
    assert typography.oswald == "Oswald"
    assert typography.oswald_style
    visible_roles = (
        TypographyRole.DISPLAY,
        TypographyRole.UI_LABEL,
        TypographyRole.UI_CONTROL,
        TypographyRole.METRIC,
        TypographyRole.INPUT,
        TypographyRole.HERO_FINANCIAL_VALUE,
        TypographyRole.PRIMARY_MONEY_VALUE,
        TypographyRole.METRIC_VALUE,
        TypographyRole.METRIC_LABEL,
        TypographyRole.SUPPORTING_TEXT,
        TypographyRole.INPUT_VALUE,
        TypographyRole.SECTION_HEADING,
    )
    assert {typography.family(role) for role in visible_roles} == {"Oswald"}
    oswald_font = QFont(typography.oswald)
    oswald_font.setPixelSize(16)
    raw_font = QRawFont.fromFont(oswald_font)
    required_codepoints = (
        0x041F, 0x0420, 0x0418, 0x0411, 0x042B, 0x041B, 0x042C,
        0x041E, 0x0414, 0x0410, 0x0416, 0x0421, 0x0415, 0x0422,
        0x042F, 0x041C, 0x041E, 0x0421, 0x0422, 0x042C,
        0x0030, 0x0031, 0x0032, 0x0035, 0x0037, 0x0039,
        0x0020, 0x002E, 0x002B, 0x002D, 0x0025,
        0x0050, 0x004C, 0x004E, 0x0042, 0x0059, 0x0058, 0x0078,
    )
    assert [codepoint for codepoint in set(required_codepoints) if not raw_font.supportsCharacter(codepoint)] == []


def test_typography_scale_prioritizes_primary_money_values() -> None:
    assert Typography.pixel_size(TypographyRole.HERO_FINANCIAL_VALUE) == 31
    assert Typography.pixel_size(TypographyRole.PRIMARY_MONEY_VALUE) == 26
    assert Typography.pixel_size(TypographyRole.METRIC_VALUE) == 21
    assert Typography.pixel_size(TypographyRole.METRIC_LABEL) == 15
    assert Typography.pixel_size(TypographyRole.SUPPORTING_TEXT) == 13
    assert Typography.pixel_size(TypographyRole.INPUT_VALUE) == 26
    assert Typography.pixel_size(TypographyRole.SECTION_HEADING) == 19
    assert Typography.pixel_size(TypographyRole.HERO_FINANCIAL_VALUE) > Typography.pixel_size(
        TypographyRole.PRIMARY_MONEY_VALUE
    )
    assert Typography.pixel_size(TypographyRole.PRIMARY_MONEY_VALUE) > Typography.pixel_size(
        TypographyRole.METRIC_VALUE
    )
    assert Typography.pixel_size(TypographyRole.METRIC_VALUE) > Typography.pixel_size(
        TypographyRole.METRIC_LABEL
    )
    assert Typography.pixel_size(TypographyRole.INPUT_VALUE) > Typography.pixel_size(
        TypographyRole.METRIC_VALUE
    )


def test_exchange_rate_editor_fits_representative_value() -> None:
    app = QApplication.instance() or QApplication([])
    typography = load_typography(lambda relative: Path(relative))
    app.setStyleSheet(build_stylesheet(typography))
    root = QWidget()
    root.setObjectName("catalogRoot")
    editor = QLineEdit(root)
    editor.setObjectName("exchangeRate")
    editor.setFixedWidth(100)
    editor.setText("0.8500")
    editor.show()
    app.processEvents()

    horizontal_padding = 18
    frame_width = 1
    usable_width = editor.width() - horizontal_padding - (frame_width * 2)
    assert QFontMetrics(editor.font()).horizontalAdvance(editor.text()) <= usable_width

    editor.deleteLater()
    root.deleteLater()
    app.processEvents()


def test_arbitrary_period_keeps_purchase_and_sale_months_separate():
    with make_session() as session:
        mine, _ = PortfolioRepository(session).ensure_default_portfolios()
        item(session, mine.id, date(2026, 1, 30), sale="200.00", sold=date(2026, 2, 2))
        report = AnalyticsService(ItemRepository(session)).report(
            mine.id, AnalyticsPeriod(date(2026, 1, 1), date(2026, 2, 28))
        )
        assert report.metrics.invested == Decimal("85.00")
        assert report.metrics.revenue == Decimal("200.00")
        assert [month.invested for month in report.monthly] == [Decimal("85.00"), Decimal("0.00")]
        assert [month.revenue for month in report.monthly] == [Decimal("0.00"), Decimal("200.00")]


def test_period_presets_have_expected_calendar_ranges():
    with make_session() as session:
        service = AnalyticsService(ItemRepository(session))
        reference = date(2026, 9, 12)
        assert service.resolve_period(PeriodPreset.CURRENT_MONTH, reference_date=reference).start_date == date(2026, 9, 1)
        assert service.resolve_period(PeriodPreset.PREVIOUS_MONTH, reference_date=reference).start_date == date(2026, 8, 1)
        assert service.resolve_period(PeriodPreset.THREE_MONTHS, reference_date=reference).start_date == date(2026, 7, 1)
        assert service.resolve_period(PeriodPreset.SIX_MONTHS, reference_date=reference).start_date == date(2026, 4, 1)
        assert service.resolve_period(PeriodPreset.CURRENT_YEAR, reference_date=reference).start_date == date(2026, 1, 1)


def test_expenses_sum_across_months_and_profit_formulas():
    with make_session() as session:
        mine, _ = PortfolioRepository(session).ensure_default_portfolios()
        item(session, mine.id, date(2026, 1, 2), sale="200.00", sold=date(2026, 1, 8))
        item(session, mine.id, date(2026, 2, 2), sale="300.00", sold=date(2026, 2, 8))
        repo = ItemRepository(session)
        repo.set_monthly_expense(mine.id, 2026, 1, Decimal("10"))
        repo.set_monthly_expense(mine.id, 2026, 2, Decimal("20"))
        metrics = AnalyticsService(repo).detailed_metrics(
            mine.id, start_date=date(2026, 1, 1), end_date=date(2026, 2, 28)
        )
        assert metrics.expenses == Decimal("30.00")
        assert metrics.realized_profit == Decimal("330.00")
        assert metrics.net_profit == Decimal("300.00")
        assert metrics.roi == Decimal("194.12")
        assert metrics.roi_after_expenses == Decimal("176.47")


def test_other_income_and_advertising_flow_through_detailed_analytics_only_as_defined():
    with make_session() as session:
        mine, _ = PortfolioRepository(session).ensure_default_portfolios()
        item(session, mine.id, date(2026, 9, 2), cost="400", sale="1000", sold=date(2026, 9, 10))
        repo = ItemRepository(session)
        repo.set_monthly_expense(mine.id, 2026, 9, Decimal("100"))
        repo.set_monthly_other_income(mine.id, 2026, 9, Decimal("150"))
        repo.set_monthly_advertising(mine.id, 2026, 9, Decimal("50"))

        metrics = AnalyticsService(repo).detailed_metrics(
            mine.id, AnalyticsPeriod(date(2026, 9, 1), date(2026, 9, 30))
        )
        assert metrics.revenue == Decimal("1150.00")
        assert metrics.realized_profit == Decimal("600.00")
        assert metrics.net_profit == Decimal("700.00")
        assert metrics.sold_count == 1
        assert metrics.average_sale == Decimal("1000.00")


def test_zero_sale_is_counted_and_cancelled_sale_is_not():
    with make_session() as session:
        mine, _ = PortfolioRepository(session).ensure_default_portfolios()
        zero_sale = item(session, mine.id, date(2026, 9, 1), cost="29.75", sale="0", sold=date(2026, 9, 10))
        cancelled = item(session, mine.id, date(2026, 9, 2), cost="40")
        repository = ItemRepository(session)
        repository.cancel_sale(cancelled)
        metrics = AnalyticsService(repository).monthly_metrics(mine.id, 2026, 9)
        assert zero_sale.sale_price_byn == Decimal("0")
        assert metrics.sold_count == 1
        assert metrics.revenue == Decimal("0.00")
        assert metrics.realized_profit == Decimal("-29.75")


def test_averages_best_worst_days_and_warehouse():
    with make_session() as session:
        mine, _ = PortfolioRepository(session).ensure_default_portfolios()
        item(session, mine.id, date(2026, 1, 1), sale="170", sold=date(2026, 1, 11))
        item(session, mine.id, date(2026, 1, 1), sale="340", sold=date(2026, 1, 21), cost="100")
        item(session, mine.id, date(2026, 1, 5), cost="42")
        metrics = AnalyticsService(ItemRepository(session)).detailed_metrics(
            mine.id, AnalyticsPeriod(date(2026, 1, 1), date(2026, 1, 31))
        )
        assert metrics.average_sale_days == Decimal("15.00")
        assert metrics.best_x == Decimal("3.40")
        assert metrics.worst_x == Decimal("2.00")
        assert metrics.average_cost == Decimal("75.67")
        assert metrics.average_sale == Decimal("255.00")
        assert metrics.average_profit == Decimal("162.50")
        assert metrics.in_stock_count == 1
        assert metrics.warehouse_value == Decimal("42.00")


def test_soft_delete_portfolio_scope_and_empty_data():
    with make_session() as session:
        mine, friend = PortfolioRepository(session).ensure_default_portfolios()
        deleted = item(session, mine.id, date(2026, 1, 1), sale="500", sold=date(2026, 1, 2))
        ItemRepository(session).soft_delete(deleted)
        item(session, friend.id, date(2026, 1, 1), sale="100", sold=date(2026, 1, 2))
        service = AnalyticsService(ItemRepository(session))
        empty = service.detailed_metrics(mine.id, AnalyticsPeriod(date(2026, 1, 1), date(2026, 1, 31)))
        assert empty.revenue == Decimal("0.00")
        assert empty.average_x is None
        assert empty.roi is None
        assert service.detailed_metrics(friend.id, PeriodPreset.ALL_TIME).revenue == Decimal("100.00")


def test_analytics_kpi_groups_labels_and_semantic_tones() -> None:
    app = QApplication.instance() or QApplication([])
    with make_session() as session:
        mine, _ = PortfolioRepository(session).ensure_default_portfolios()
        item(session, mine.id, date(2026, 9, 1), cost="100", sale="0", sold=date(2026, 9, 10))
        session.commit()
        factory = sessionmaker(bind=session.bind, class_=Session, expire_on_commit=False)
        window = AnalyticsWindow(factory, mine.id)
        try:
            assert set(window.metric_labels) == {
                "revenue", "realized_profit", "net_profit", "expenses", "sold_count",
                "roi", "roi_after_expenses", "average_x", "best_x", "worst_x",
                "invested", "purchased_count", "in_stock_count", "warehouse_value",
                "average_cost", "average_sale", "average_profit", "average_sale_days",
            }
            assert window.revenue_chart.title == "ПРОДАЖИ ПО МЕСЯЦАМ"
            window.period_combo.setCurrentIndex(window.period_combo.findData(PeriodPreset.ALL_TIME))
            window.refresh()
            assert window.metric_labels["realized_profit"].property("tone") == "negative"
            assert window.metric_labels["net_profit"].property("tone") == "negative"
            assert window.metric_labels["revenue"].property("tone") == "neutral"
            assert window.metric_labels["sold_count"].property("tone") == "neutral"
        finally:
            window.close()
            app.processEvents()


def test_analytics_neon_ui_preserves_structure_font_and_rendered_tones() -> None:
    app = QApplication.instance() or QApplication([])
    previous_stylesheet = app.styleSheet()
    app.setStyleSheet(build_stylesheet("Onest"))
    with make_session() as session:
        mine, _ = PortfolioRepository(session).ensure_default_portfolios()
        item(session, mine.id, date(2026, 9, 1), cost="100", sale="200", sold=date(2026, 9, 10))
        session.commit()
        factory = sessionmaker(bind=session.bind, class_=Session, expire_on_commit=False)
        window = AnalyticsWindow(factory, mine.id)
        window.show()
        app.processEvents()
        try:
            assert window.centralWidget().objectName() == "analyticsRoot"
            assert window.portfolio_tabs.objectName() == "analyticsPortfolioTabs"
            assert window.period_combo.objectName() == "analyticsPeriodCombo"
            assert window.period_combo.count() == 6
            assert window.metric_labels["net_profit"].property("tone") == "positive"
            assert window.metric_labels["expenses"].property("tone") == "amber"
            assert window.metric_labels["net_profit"].palette().color(
                window.metric_labels["net_profit"].foregroundRole()
            ).getRgb()[:3] == (118, 198, 154)
            assert window.metric_labels["expenses"].palette().color(
                window.metric_labels["expenses"].foregroundRole()
            ).getRgb()[:3] == (201, 169, 104)
            title = window.findChild(QWidget, "analyticsTitle")
            assert title is not None
            assert title.font().family() == "Oswald"
            assert title.font().pixelSize() == 29
        finally:
            window.close()
            app.processEvents()
            app.setStyleSheet(previous_stylesheet)


def test_catalogue_monthly_sales_label_uses_sales_terminology() -> None:
    app = QApplication.instance() or QApplication([])
    with make_session() as session:
        mine, _ = PortfolioRepository(session).ensure_default_portfolios()
        item(session, mine.id, date(2026, 9, 1), sale="200", sold=date(2026, 9, 10))
        factory = sessionmaker(bind=session.bind, class_=Session, expire_on_commit=False)
        window = MainWindow.__new__(MainWindow)
        window.session_factory = factory
        window.current_portfolio_id = mine.id
        widget = window._month_group(
            session,
            2026,
            9,
            [],
            AnalyticsService(ItemRepository(session)).monthly_metrics(mine.id, 2026, 9),
        )
        try:
            assert "ВЫРУЧКА" not in [label.text() for label in widget.findChildren(QLabel)]
            assert "ПРОДАЖИ" in [label.text() for label in widget.findChildren(QLabel)]
        finally:
            widget.deleteLater()
            app.processEvents()


def test_catalogue_month_group_exposes_three_monthly_financial_fields() -> None:
    app = QApplication.instance() or QApplication([])
    with make_session() as session:
        mine, _ = PortfolioRepository(session).ensure_default_portfolios()
        repo = ItemRepository(session)
        repo.set_monthly_expense(mine.id, 2026, 9, Decimal("10"))
        repo.set_monthly_other_income(mine.id, 2026, 9, Decimal("20"))
        repo.set_monthly_advertising(mine.id, 2026, 9, Decimal("30"))
        factory = sessionmaker(bind=session.bind, class_=Session, expire_on_commit=False)
        window = MainWindow.__new__(MainWindow)
        window.session_factory = factory
        window.current_portfolio_id = mine.id
        widget = window._month_group(
            session,
            2026,
            9,
            [],
            AnalyticsService(repo).monthly_metrics(mine.id, 2026, 9),
        )
        try:
            assert {
                field.objectName()
                for field in widget.findChildren(QLineEdit)
            } == {"monthlyExpense", "monthlyOtherIncome", "monthlyAdvertising"}
            assert {label.text() for label in widget.findChildren(QLabel)} >= {
                "РАСХОДЫ", "ДРУГИЕ ДОХОДЫ", "РЕКЛАМА"
            }
        finally:
            widget.deleteLater()
            app.processEvents()


def test_catalogue_months_include_income_only_periods() -> None:
    periods = MainWindow._months([], [(2025, 12)])
    assert (2025, 12) in periods

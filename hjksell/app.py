"""Application bootstrap."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QApplication

from .database.connection import initialize_database
from .logging_config import configure_logging
from .ui.main_window import MainWindow


def load_catalog_font() -> str | None:
    """Load the bundled Catalog font and return its registered family."""

    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
    font_path = base / "assets" / "fonts" / "onest" / "Onest[wght].ttf"
    font_id = QFontDatabase.addApplicationFont(str(font_path))
    if font_id < 0:
        logging.getLogger(__name__).warning("Catalog font could not be loaded: %s", font_path)
        return None
    families = QFontDatabase.applicationFontFamilies(font_id)
    return families[0] if families else None


def build_stylesheet(catalog_font_family: str | None = None) -> str:
    """Return the premium dark graphite theme."""

    catalog_font = catalog_font_family or "Segoe UI Variable"
    return """
        QMainWindow, QWidget {
            background-color: #0e1117;
            color: #f1f3f5;
            font-family: "Segoe UI Variable", "Segoe UI";
            font-size: 13px;
        }
        QWidget#catalogRoot {
            background-color: #09090b;
            color: #fcf4ff;
            font-family: "%s", "Segoe UI Variable", "Segoe UI";
        }
        QTabBar#catalogPortfolioTabs::tab {
            background: #101014;
            color: #858094;
            border: 1px solid #24202d;
            border-radius: 7px;
            padding: 9px 16px;
            margin-right: 4px;
            font-size: 13px;
            font-weight: 700;
        }
        QTabBar#catalogPortfolioTabs::tab:hover {
            background: #17141e;
            color: #d9c9ee;
        }
        QTabBar#catalogPortfolioTabs::tab:selected {
            background: #241737;
            color: #f5eaff;
            border-color: #8a55c7;
        }
        QToolButton#catalogRenameButton {
            background: #15121b;
            border: 1px solid #292132;
            border-radius: 7px;
            color: #bfa8d8;
            padding: 6px 9px;
            font-size: 15px;
        }
        QToolButton#catalogRenameButton:hover {
            background: #21172d;
            color: #f0ddff;
            border-color: #8a55c7;
        }
        QLabel#catalogRateLabel {
            color: #91899c;
            font-size: 11px;
            font-weight: 700;
        }
        QLabel#catalogFilterLabel {
            color: #91899c;
            font-size: 10px;
            font-weight: 700;
            padding-right: 7px;
        }
        QToolButton#catalogFilterButton {
            background: #101014;
            border: 1px solid #211e28;
            border-radius: 6px;
            color: #87818f;
            padding: 8px 12px;
            font-size: 10px;
            font-weight: 700;
        }
        QToolButton#catalogFilterButton:hover {
            background: #18151e;
            color: #d8cbe4;
        }
        QToolButton#catalogFilterButton:checked {
            background: #2b1b40;
            border-color: #6e478e;
            color: #f5eaff;
        }
        QGroupBox#catalogMonthGroup {
            background-color: #101014;
            border: 1px solid #25212e;
            border-radius: 11px;
            margin-top: 15px;
            padding: 12px 10px 10px;
        }
        QGroupBox#catalogMonthGroup::title {
            color: #ded2e9;
        }
        QWidget#catalogKpiStrip {
            background-color: #15121b;
            border: 1px solid #211c2a;
            border-radius: 9px;
        }
        QWidget#catalogKpiStrip QWidget {
            background: transparent;
            border: none;
        }
        QWidget#catalogKpiStrip QLabel#catalogKpiPrimaryValue {
            color: #f5eaff;
            font-size: 18px;
            font-weight: 700;
        }
        QWidget#catalogKpiStrip QLabel#profitValue {
            font-size: 18px;
        }
        QWidget#catalogRoot QWidget#itemCard {
            background-color: #17151e;
            border: 1px solid #332b3d;
            border-radius: 10px;
        }
        QWidget#catalogRoot QWidget#itemCard:hover {
            background-color: #191620;
            border-color: #493460;
        }
        QWidget#catalogRoot QLineEdit#saleInput:focus {
            border-color: #a66be0;
            background: #15101c;
        }
        QWidget#catalogRoot QLabel#catalogMetricValue[tone="positive"] {
            color: #76c69a;
            font-size: 16px;
            font-weight: 700;
        }
        QWidget#catalogRoot QLabel#catalogMetricValue[tone="negative"] {
            color: #d98282;
            font-size: 16px;
            font-weight: 700;
        }
        QWidget#catalogRoot QLabel#catalogMetricValue[tone="neutral"] {
            color: #f4f7fb;
            font-size: 16px;
            font-weight: 600;
        }
        QWidget#catalogRoot QLineEdit#exchangeRate,
        QWidget#catalogRoot QLineEdit#monthlyExpense,
        QWidget#catalogRoot QLineEdit#saleInput {
            border: 1px solid #393340;
            border-radius: 6px;
            padding: 7px 9px;
            background: #101014;
            color: #f5effa;
        }
        QWidget#catalogRoot QLineEdit#exchangeRate:focus,
        QWidget#catalogRoot QLineEdit#monthlyExpense:focus,
        QWidget#catalogRoot QLineEdit#saleInput:focus {
            border-color: #a66be0;
            background: #15101c;
        }
        QLabel#catalogBrand {
            background: transparent;
        }
        QWidget#catalogRoot QWidget#catalogBrand {
            font-family: "Onest";
            font-size: 29px;
            font-weight: 800;
        }
        QWidget#catalogHeader {
            background: transparent;
        }
        QWidget#catalogActions {
            background: transparent;
        }
        QPushButton#catalogSecondaryButton {
            background: #15151b;
            border: 1px solid #2a2631;
            border-radius: 7px;
            color: #d7cfdf;
            padding: 8px 12px;
            font-weight: 700;
        }
        QPushButton#catalogSecondaryButton:hover {
            background: #1c1922;
            border-color: #544766;
            color: #f4eaff;
        }
        QPushButton#catalogPrimaryButton {
            background: #7f4eb2;
            border: 1px solid #a36bd1;
            border-radius: 7px;
            color: #fffaff;
            padding: 8px 14px;
            font-weight: 800;
        }
        QPushButton#catalogPrimaryButton:hover {
            background: #9961cc;
            border-color: #c08af0;
        }
        QToolButton#catalogIconButton {
            background: transparent;
            border: none;
            border-radius: 6px;
            color: #938b9d;
            padding: 7px;
            font-size: 16px;
        }
        QToolButton#catalogIconButton:hover {
            background: #1d1824;
            color: #e9d7fb;
        }
        QTabBar::tab {
            background: transparent;
            color: #7f8996;
            border: none;
            border-bottom: 2px solid transparent;
            padding: 8px 14px 9px;
            font-size: 13px;
            font-weight: 600;
        }
        QTabBar::tab:selected {
            color: #f1f3f5;
            border-bottom-color: #7da6d8;
        }
        QLabel#title {
            color: #ffffff;
            font-size: 22px;
            font-weight: 700;
        }
        QLabel#subtitle {
            color: #7f8996;
            font-size: 12px;
        }
        QGroupBox {
            background-color: #151920;
            border: 1px solid #252c36;
            border-radius: 8px;
            margin-top: 15px;
            padding: 12px 10px 10px;
        }
        QWidget#analyticsRoot {
            background-color: #09090b;
            color: #f4f1f7;
            font-family: "Onest", "Segoe UI Variable", "Segoe UI";
        }
        QWidget#analyticsRoot QWidget#analyticsHeader {
            background: transparent;
        }
        QWidget#analyticsRoot QLabel#analyticsTitle {
            background: transparent;
        }
        QWidget#analyticsRoot QTabBar#analyticsPortfolioTabs::tab {
            background: #101014;
            color: #858094;
            border: 1px solid #24202d;
            border-radius: 7px;
            padding: 8px 15px;
            margin-right: 4px;
            font-weight: 700;
        }
        QWidget#analyticsRoot QTabBar#analyticsPortfolioTabs::tab:selected {
            background: #241737;
            color: #f5eaff;
            border-color: #8a55c7;
        }
        QWidget#analyticsRoot QLabel#analyticsControlLabel {
            color: #91899c;
            font-size: 10px;
            font-weight: 700;
        }
        QWidget#analyticsRoot QComboBox#analyticsPeriodCombo {
            background: #101014;
            color: #e9e1ef;
            border: 1px solid #393340;
            border-radius: 7px;
            padding: 7px 28px 7px 10px;
            min-width: 120px;
        }
        QWidget#analyticsRoot QComboBox#analyticsPeriodCombo:focus,
        QWidget#analyticsRoot QComboBox#analyticsPeriodCombo:on {
            border-color: #a66be0;
        }
        QWidget#analyticsRoot QComboBox#analyticsPeriodCombo QAbstractItemView {
            background: #15121b;
            color: #f4eaff;
            selection-background-color: #3a2451;
            selection-color: #ffffff;
        }
        QWidget#analyticsRoot QPushButton#analyticsBack {
            background: #15151b;
            border: 1px solid #2a2631;
            border-radius: 7px;
            padding: 8px 12px;
            color: #d7cfdf;
            font-weight: 700;
        }
        QWidget#analyticsRoot QPushButton#analyticsBack:hover {
            background: #21172d;
            border-color: #8a55c7;
            color: #f4eaff;
        }
        QWidget#analyticsRoot QGroupBox {
            background-color: #111116;
            border: 1px solid #2b2634;
            border-radius: 11px;
            margin-top: 14px;
        }
        QWidget#analyticsRoot QGroupBox#analyticsPrimarySection {
            background-color: #17121f;
            border-color: #49325f;
        }
        QWidget#analyticsRoot QGroupBox#analyticsSection {
            background-color: #111116;
            border-color: #2b2634;
        }
        QWidget#analyticsRoot QGroupBox::title {
            subcontrol-origin: margin;
            left: 12px;
            padding: 0 7px;
            color: #dfd0ec;
            font-size: 14px;
            font-weight: 700;
        }
        QWidget#analyticsRoot QWidget#analyticsMetricCell {
            background: #15121b;
            border: 1px solid #27212f;
            border-radius: 8px;
        }
        QWidget#analyticsRoot QWidget#analyticsPrimarySection QWidget#analyticsMetricCell {
            background: #1c1625;
            border-color: #3d2b4b;
        }
        QWidget#analyticsRoot QLabel#analyticsMetricLabel {
            color: #91899c;
            font-size: 10px;
            font-weight: 700;
        }
        QWidget#analyticsRoot QLabel#analyticsValue {
            color: #f4f7fb;
            font-size: 16px;
            font-weight: 700;
        }
        QWidget#analyticsRoot QLabel#analyticsPrimaryValue {
            color: #f4f7fb;
            font-size: 19px;
            font-weight: 700;
        }
        QWidget#analyticsRoot QLabel#analyticsValue[tone="positive"],
        QWidget#analyticsRoot QLabel#analyticsPrimaryValue[tone="positive"] {
            color: #76c69a;
        }
        QWidget#analyticsRoot QLabel#analyticsValue[tone="negative"],
        QWidget#analyticsRoot QLabel#analyticsPrimaryValue[tone="negative"] {
            color: #d98282;
        }
        QWidget#analyticsRoot QLabel#analyticsValue[tone="neutral"],
        QWidget#analyticsRoot QLabel#analyticsPrimaryValue[tone="neutral"] {
            color: #f4f7fb;
        }
        QWidget#analyticsRoot QLabel#analyticsValue[tone="amber"],
        QWidget#analyticsRoot QLabel#analyticsPrimaryValue[tone="amber"] {
            color: #c9a968;
        }
        QWidget#analyticsRoot QLabel#analyticsSubtitle {
            color: #91899c;
            font-size: 11px;
            padding-bottom: 2px;
        }
        QWidget#analyticsRoot QWidget#analyticsChart {
            background: #101014;
            border: 1px solid #2b2634;
            border-radius: 10px;
        }
        QWidget#itemCard {
            background-color: #1a1f27;
            border: 1px solid #252d38;
            border-radius: 8px;
        }
        QWidget#itemCard:hover {
            background-color: #202631;
            border-color: #344152;
        }
        QLabel#emptyState {
            color: #aab4c1;
            font-size: 18px;
        }
        QLabel#sectionLabel, QLabel#metricLabel {
            color: #7f8996;
            font-size: 10px;
            font-weight: 600;
        }
        QLabel#metricValue {
            color: #f4f7fb;
            font-size: 16px;
            font-weight: 600;
        }
        QLabel#profitValue {
            color: #76c69a;
            font-size: 16px;
            font-weight: 700;
        }
        QLabel#lossValue {
            color: #d98282;
            font-size: 16px;
            font-weight: 700;
        }
        QLabel#statusSold {
            color: #76c69a;
            font-weight: 600;
        }
        QLabel#statusStock {
            color: #91a7c4;
            font-weight: 600;
        }
        QLabel#statusNoRevenue {
            color: #c9a968;
            font-weight: 600;
        }
        QLineEdit#saleInput, QLineEdit#exchangeRate, QLineEdit#monthlyExpense {
            border: 1px solid #334052;
            border-radius: 5px;
            padding: 6px 8px;
            background: #11151c;
            color: #f1f3f5;
        }
        QLineEdit#saleInput {
            color: #f4f7fb;
            font-size: 16px;
            font-weight: 600;
        }
        QLineEdit#saleInput:focus, QLineEdit#exchangeRate:focus, QLineEdit#monthlyExpense:focus {
            border-color: #7199c7;
        }
        QToolButton#filterButton, QPushButton#primaryButton {
            background: transparent;
            border: none;
            color: #7f8996;
            padding: 7px 10px;
            font-size: 11px;
            font-weight: 700;
        }
        QToolButton#filterButton:checked {
            color: #f1f3f5;
            border-bottom: 2px solid #7da6d8;
        }
        QPushButton#primaryButton {
            background: #6f94bf;
            color: #0e1117;
            border-radius: 5px;
            padding: 8px 15px;
        }
        QPushButton#primaryButton:hover {
            background: #86a9d2;
        }
        QToolButton#itemMenu {
            background: transparent;
            border: none;
            color: #7f8996;
            font-size: 20px;
        }
        QPushButton {
            background: #202833;
            border: 1px solid #344152;
            border-radius: 5px;
            padding: 6px 11px;
            color: #dce5ef;
        }
        QPushButton:hover {
            background: #293442;
        }
    """ % catalog_font


def main() -> int:
    """Start HJKsell and return the Qt exit code."""

    paths = configure_logging()
    logger = logging.getLogger(__name__)
    logger.info("Starting HJKsell")
    _engine, session_factory = initialize_database(paths)

    application = QApplication(sys.argv)
    application.setApplicationName("HJKsell")
    catalog_font = load_catalog_font()
    application.setStyleSheet(build_stylesheet(catalog_font))

    window = MainWindow(session_factory=session_factory, paths=paths)
    window.show()
    return application.exec()

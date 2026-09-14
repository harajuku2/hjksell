"""Application bootstrap."""

from __future__ import annotations

import logging
import sys

from PySide6.QtWidgets import QApplication

from .database.connection import initialize_database
from .logging_config import configure_logging
from .ui.main_window import MainWindow


def build_stylesheet() -> str:
    """Return the premium dark graphite theme."""

    return """
        QMainWindow, QWidget {
            background-color: #0e1117;
            color: #f1f3f5;
            font-family: "Segoe UI Variable", "Segoe UI";
            font-size: 13px;
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
        QGroupBox#analyticsPrimarySection {
            background-color: #181e27;
            border-color: #344152;
        }
        QGroupBox#analyticsSection {
            background-color: #151920;
            border-color: #252c36;
        }
        QLabel#analyticsTitle {
            color: #ffffff;
            font-size: 22px;
            font-weight: 700;
        }
        QLabel#analyticsSubtitle {
            color: #7f8996;
            font-size: 12px;
            padding-bottom: 3px;
        }
        QLabel#analyticsValue {
            color: #f4f7fb;
            font-size: 17px;
            font-weight: 700;
        }
        QLabel#analyticsPrimaryValue {
            color: #f4f7fb;
            font-size: 21px;
            font-weight: 700;
        }
        QLabel#analyticsMetricLabel {
            color: #7f8996;
            font-size: 10px;
            font-weight: 600;
        }
        QLabel#analyticsValue[tone="positive"], QLabel#analyticsPrimaryValue[tone="positive"] {
            color: #76c69a;
        }
        QLabel#analyticsValue[tone="negative"], QLabel#analyticsPrimaryValue[tone="negative"] {
            color: #d98282;
        }
        QLabel#analyticsValue[tone="neutral"], QLabel#analyticsPrimaryValue[tone="neutral"] {
            color: #f4f7fb;
        }
        QLabel#analyticsValue[tone="amber"], QLabel#analyticsPrimaryValue[tone="amber"] {
            color: #c9a968;
        }
        QPushButton#analyticsBack {
            background: #202833;
            border: 1px solid #344152;
            border-radius: 5px;
            padding: 8px 12px;
            color: #dce5ef;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 12px;
            padding: 0 7px;
            color: #dfe5ed;
            font-size: 14px;
            font-weight: 700;
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
    """


def main() -> int:
    """Start HJKsell and return the Qt exit code."""

    paths = configure_logging()
    logger = logging.getLogger(__name__)
    logger.info("Starting HJKsell")
    _engine, session_factory = initialize_database(paths)

    application = QApplication(sys.argv)
    application.setApplicationName("HJKsell")
    application.setStyleSheet(build_stylesheet())

    window = MainWindow(session_factory=session_factory, paths=paths)
    window.show()
    return application.exec()

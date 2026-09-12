"""Application bootstrap."""

from __future__ import annotations

import logging
import sys

from PySide6.QtWidgets import QApplication

from .database.connection import initialize_database
from .logging_config import configure_logging
from .ui.main_window import MainWindow


def build_stylesheet() -> str:
    """Return the initial dark graphite theme."""

    return """
        QMainWindow, QWidget {
            background-color: #202225;
            color: #f1f3f5;
            font-family: "Segoe UI";
            font-size: 14px;
        }
        QLabel#title {
            color: #ffffff;
            font-size: 32px;
            font-weight: 600;
        }
        QLabel#subtitle {
            color: #aeb4bd;
            font-size: 16px;
            margin-top: 8px;
        }
        QGroupBox {
            background-color: #292c31;
            border: 1px solid #3a3f46;
            border-radius: 6px;
            margin-top: 12px;
            padding: 8px;
            font-weight: 600;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 5px;
            color: #dfe3e8;
        }
        QWidget#itemCard {
            background-color: #30343a;
            border: 1px solid #3c424a;
            border-radius: 5px;
        }
        QLabel#monthlyStats {
            color: #bdc4cd;
            font-size: 13px;
        }
        QLabel#emptyState {
            color: #9ba3ad;
            font-size: 18px;
        }
        QLineEdit#saleInput, QLineEdit#exchangeRate {
            border: 1px solid #536d91;
            border-radius: 4px;
            padding: 5px;
            background: #24272b;
        }
        QPushButton {
            padding: 5px 11px;
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

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
    """


def main() -> int:
    """Start HJKsell and return the Qt exit code."""

    paths = configure_logging()
    logger = logging.getLogger(__name__)
    logger.info("Starting HJKsell")
    initialize_database(paths)

    application = QApplication(sys.argv)
    application.setApplicationName("HJKsell")
    application.setStyleSheet(build_stylesheet())

    window = MainWindow()
    window.show()
    return application.exec()

"""Application logging setup."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from .config import AppPaths, ensure_app_directories


def configure_logging(paths: AppPaths | None = None) -> AppPaths:
    """Configure console and rotating file logging without logging secrets."""

    resolved_paths = ensure_app_directories(paths)
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    for logger_name in ("httpx", "httpcore"):
        transport_logger = logging.getLogger(logger_name)
        transport_logger.setLevel(logging.WARNING)
        transport_logger.disabled = True

    if not root_logger.handlers:
        formatter = logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        file_handler = RotatingFileHandler(
            resolved_paths.log_file,
            maxBytes=2_000_000,
            backupCount=3,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
        root_logger.addHandler(logging.StreamHandler())

    return resolved_paths

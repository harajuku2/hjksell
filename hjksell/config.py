"""Centralized application paths and configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AppPaths:
    """Filesystem locations used by HJKsell."""

    root: Path
    data: Path
    photos: Path
    logs: Path
    database: Path
    log_file: Path


def get_app_paths() -> AppPaths:
    """Return paths under the Windows local application data directory."""

    local_app_data = os.environ.get("LOCALAPPDATA")
    if not local_app_data:
        local_app_data = str(Path.home() / "AppData" / "Local")

    root = Path(local_app_data) / "HJKsell"
    data = root / "data"
    photos = data / "photos"
    logs = root / "logs"
    return AppPaths(
        root=root,
        data=data,
        photos=photos,
        logs=logs,
        database=data / "hjk_sell.db",
        log_file=logs / "app.log",
    )


def ensure_app_directories(paths: AppPaths | None = None) -> AppPaths:
    """Create required local directories and return the resulting paths."""

    resolved_paths = paths or get_app_paths()
    for directory in (resolved_paths.root, resolved_paths.data, resolved_paths.photos, resolved_paths.logs):
        directory.mkdir(parents=True, exist_ok=True)
    return resolved_paths

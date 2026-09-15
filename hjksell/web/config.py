"""Explicit filesystem boundary for the isolated web development runtime."""

from __future__ import annotations

from pathlib import Path

from ..config import AppPaths


def web_dev_paths(root: Path | None = None) -> AppPaths:
    """Build paths under the repository-local .web-dev directory."""

    resolved_root = root or Path(__file__).resolve().parents[2] / ".web-dev"
    data = resolved_root / "data"
    logs = resolved_root / "logs"
    return AppPaths(
        root=resolved_root,
        data=data,
        photos=data / "photos",
        logs=logs,
        database=data / "hjk_sell_web_dev.db",
        log_file=logs / "web.log",
    )

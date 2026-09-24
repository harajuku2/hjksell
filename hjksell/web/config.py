"""Explicit filesystem boundary for the isolated web development runtime."""

from __future__ import annotations

import os
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


def web_production_paths() -> AppPaths:
    """Resolve the explicit persistent data mount required by public hosting."""

    configured_root = os.environ.get("HJKSELL_DATA_DIR", "").strip()
    if not configured_root:
        raise RuntimeError("Для production задайте HJKSELL_DATA_DIR на постоянный диск хостинга.")
    configured_path = Path(configured_root).expanduser()
    if not configured_path.is_absolute():
        raise RuntimeError("HJKSELL_DATA_DIR должен быть абсолютным путём.")
    root = configured_path.resolve()
    repository_root = Path(__file__).resolve().parents[2]
    local_app_data = os.environ.get("LOCALAPPDATA")
    forbidden_roots = [repository_root]
    if local_app_data:
        forbidden_roots.append((Path(local_app_data) / "HJKsell").resolve())
    if any(root == forbidden or forbidden in root.parents for forbidden in forbidden_roots):
        raise RuntimeError("Публичные данные должны находиться отдельно от репозитория и локальной базы Windows.")
    data = root / "data"
    logs = root / "logs"
    return AppPaths(
        root=root,
        data=data,
        photos=data / "photos",
        logs=logs,
        database=data / "hjk_sell.db",
        log_file=logs / "web.log",
    )

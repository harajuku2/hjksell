"""Non-destructive schema initialization for source and packaged builds."""

from __future__ import annotations

import sys
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

from ..config import AppPaths


def migrations_path() -> Path:
    """Locate bundled Alembic scripts in a source tree or PyInstaller build."""

    bundle_root = getattr(sys, "_MEIPASS", None)
    return Path(bundle_root) / "alembic" if bundle_root else Path(__file__).resolve().parents[2] / "alembic"


def upgrade_database(engine: Engine, paths: AppPaths) -> None:
    """Apply migrations to a new database and preserve legacy databases."""

    inspector = inspect(engine)
    if not inspector.has_table("alembic_version"):
        # Older HJKsell releases created the current model directly. Preserve
        # those databases and mark them at the current migration head.
        if inspector.has_table("portfolios"):
            config = Config()
            config.set_main_option("script_location", str(migrations_path()))
            config.set_main_option("sqlalchemy.url", f"sqlite:///{paths.database.as_posix()}")
            command.stamp(config, "head")
            _ensure_head_marker(engine)
            return
    config = Config()
    config.set_main_option("script_location", str(migrations_path()))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{paths.database.as_posix()}")
    command.upgrade(config, "head")


def _ensure_head_marker(engine: Engine) -> None:
    """Persist the migration head when stamping a legacy schema."""

    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE IF NOT EXISTS alembic_version "
                "(version_num VARCHAR(32) NOT NULL)"
            )
        )
        connection.execute(text("DELETE FROM alembic_version"))
        connection.execute(
            text("INSERT INTO alembic_version (version_num) VALUES (:version)"),
            {"version": "0004_discovered_telegram_channels"},
        )

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
            _ensure_legacy_monthly_income_columns(engine)
            _ensure_legacy_currency_schema(engine)
            _ensure_legacy_item_expense_column(engine)
            _ensure_legacy_automatic_expense_columns(engine)
            _ensure_legacy_portfolio_owner_column(engine)
            _ensure_legacy_channel_scope_column(engine)
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
            {"version": "0011_portfolio_scoped_discovered_channels"},
        )


def _ensure_legacy_monthly_income_columns(engine: Engine) -> None:
    """Add fields to pre-Alembic databases without rebuilding user tables."""

    columns = {column["name"] for column in inspect(engine).get_columns("monthly_expenses")}
    with engine.begin() as connection:
        for name in ("other_income_byn", "advertising_byn"):
            if name not in columns:
                connection.execute(
                    text(
                        f"ALTER TABLE monthly_expenses ADD COLUMN {name} "
                        "NUMERIC(12, 2) NOT NULL DEFAULT 0"
                    )
                )


def _ensure_legacy_currency_schema(engine: Engine) -> None:
    """Preserve old rows while adding historical currencies and portfolio defaults."""

    item_columns = {column["name"] for column in inspect(engine).get_columns("items")}
    with engine.begin() as connection:
        if "purchase_currency" not in item_columns:
            connection.execute(
                text("ALTER TABLE items ADD COLUMN purchase_currency VARCHAR(3) NOT NULL DEFAULT 'PLN'")
            )
        if "sale_currency" not in item_columns:
            connection.execute(
                text("ALTER TABLE items ADD COLUMN sale_currency VARCHAR(3) NOT NULL DEFAULT 'BYN'")
            )
        connection.execute(
            text(
                "CREATE TABLE IF NOT EXISTS portfolio_currency_settings ("
                "portfolio_id INTEGER NOT NULL PRIMARY KEY REFERENCES portfolios(id), "
                "purchase_currency VARCHAR(3) NOT NULL DEFAULT 'PLN', "
                "sale_currency VARCHAR(3) NOT NULL DEFAULT 'BYN', "
                "exchange_rate NUMERIC(14, 6) NOT NULL DEFAULT 0.8500, "
                "automatic_expense_amount NUMERIC(12, 2) NOT NULL DEFAULT 0, "
                "automatic_expense_currency VARCHAR(3) NOT NULL DEFAULT 'PLN', "
                "automatic_expense_purchase_rate NUMERIC(14, 6) NOT NULL DEFAULT 1.0000, "
                "updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP)"
            )
        )


def _ensure_legacy_item_expense_column(engine: Engine) -> None:
    """Give pre-Alembic item rows a zero purchase expense before stamping head."""

    columns = {column["name"] for column in inspect(engine).get_columns("items")}
    if "purchase_expense" in columns:
        return
    with engine.begin() as connection:
        connection.execute(
            text("ALTER TABLE items ADD COLUMN purchase_expense NUMERIC(12, 2) NOT NULL DEFAULT 0")
        )


def _ensure_legacy_automatic_expense_columns(engine: Engine) -> None:
    """Give legacy portfolio defaults an opt-in automatic expense configuration."""

    columns = {column["name"] for column in inspect(engine).get_columns("portfolio_currency_settings")}
    with engine.begin() as connection:
        if "automatic_expense_amount" not in columns:
            connection.execute(
                text(
                    "ALTER TABLE portfolio_currency_settings ADD COLUMN "
                    "automatic_expense_amount NUMERIC(12, 2) NOT NULL DEFAULT 0"
                )
            )
        if "automatic_expense_currency" not in columns:
            connection.execute(
                text(
                    "ALTER TABLE portfolio_currency_settings ADD COLUMN "
                    "automatic_expense_currency VARCHAR(3) NOT NULL DEFAULT 'PLN'"
                )
            )
            connection.execute(
                text(
                    "UPDATE portfolio_currency_settings "
                    "SET automatic_expense_currency = purchase_currency"
                )
            )
        if "automatic_expense_purchase_rate" not in columns:
            connection.execute(
                text(
                    "ALTER TABLE portfolio_currency_settings ADD COLUMN "
                    "automatic_expense_purchase_rate NUMERIC(14, 6) NOT NULL DEFAULT 1.0000"
                )
            )


def _ensure_legacy_portfolio_owner_column(engine: Engine) -> None:
    """Add nullable ownership without assigning existing local portfolios."""

    columns = {column["name"] for column in inspect(engine).get_columns("portfolios")}
    if "owner_telegram_id" in columns:
        return
    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE portfolios ADD COLUMN owner_telegram_id BIGINT"))
        connection.execute(
            text("CREATE INDEX IF NOT EXISTS ix_portfolios_owner_telegram_id ON portfolios (owner_telegram_id)")
        )


def _ensure_legacy_channel_scope_column(engine: Engine) -> None:
    """Mark existing portfolio-less channels as discoveries, not bindings."""

    columns = {column["name"] for column in inspect(engine).get_columns("telegram_channels")}
    if "is_bound" in columns:
        return
    with engine.begin() as connection:
        connection.execute(
            text("ALTER TABLE telegram_channels ADD COLUMN is_bound BOOLEAN NOT NULL DEFAULT 1")
        )
        connection.execute(text("UPDATE telegram_channels SET is_bound = 0 WHERE portfolio_id IS NULL"))

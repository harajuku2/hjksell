"""SQLAlchemy engine and database initialization."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from sqlalchemy import create_engine, inspect
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from ..config import AppPaths, ensure_app_directories
from .models import Base
from .migrations import upgrade_database


def create_engine_for_path(database_path: Path):
    """Create a SQLite engine for the supplied database path."""

    database_path.parent.mkdir(parents=True, exist_ok=True)
    return create_engine(
        f"sqlite:///{database_path.as_posix()}",
        connect_args={"check_same_thread": False},
    )


def create_session_factory(database_path: Path):
    """Create a typed session factory for a SQLite database."""

    engine = create_engine_for_path(database_path)
    return sessionmaker(bind=engine, class_=Session, expire_on_commit=False)


def initialize_database(
    paths: AppPaths | None = None,
    *,
    seed_default_portfolios: bool = True,
    session_info: dict | None = None,
) -> tuple[Engine, Callable[[], Session]]:
    """Create the schema and optionally seed desktop/development portfolios."""

    resolved_paths = ensure_app_directories(paths)
    engine = create_engine_for_path(resolved_paths.database)
    if inspect(engine).has_table("alembic_version"):
        upgrade_database(engine, resolved_paths)
        Base.metadata.create_all(engine)
    else:
        Base.metadata.create_all(engine)
        upgrade_database(engine, resolved_paths)
    factory = sessionmaker(bind=engine, class_=Session, expire_on_commit=False, info=session_info or {})

    from ..repositories.portfolio_repository import PortfolioRepository

    if seed_default_portfolios:
        with factory() as session:
            PortfolioRepository(session).ensure_default_portfolios()
            session.commit()
    return engine, factory

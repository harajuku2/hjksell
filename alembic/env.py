"""Alembic environment for future non-destructive schema migrations."""

from alembic import context
from sqlalchemy import engine_from_config, pool

from hjksell.config import get_app_paths
from hjksell.database.models import Base

config = context.config
config.set_main_option("sqlalchemy.url", f"sqlite:///{get_app_paths().database.as_posix()}")
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(url=config.get_main_option("sqlalchemy.url"), target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

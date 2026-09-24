"""Associate web portfolios with their Telegram Mini App owner."""

from alembic import op
import sqlalchemy as sa


revision = "0010_telegram_portfolio_owners"
down_revision = "0009_portfolio_automatic_expense"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("portfolios")}
    unique_constraints = inspector.get_unique_constraints("portfolios")
    has_global_name = any(constraint.get("column_names") == ["name"] for constraint in unique_constraints)
    has_owner_name = any(
        constraint.get("column_names") == ["owner_telegram_id", "name"]
        for constraint in unique_constraints
    )
    indexes = {index["name"] for index in inspector.get_indexes("portfolios")}
    with op.batch_alter_table(
        "portfolios",
        naming_convention={"uq": "uq_%(table_name)s_%(column_0_name)s"},
    ) as batch_op:
        if has_global_name:
            batch_op.drop_constraint("uq_portfolios_name", type_="unique")
        if "owner_telegram_id" not in columns:
            batch_op.add_column(sa.Column("owner_telegram_id", sa.BigInteger(), nullable=True))
        if "ix_portfolios_owner_telegram_id" not in indexes:
            batch_op.create_index("ix_portfolios_owner_telegram_id", ["owner_telegram_id"])
        if not has_owner_name:
            batch_op.create_unique_constraint("uq_portfolio_owner_name", ["owner_telegram_id", "name"])


def downgrade() -> None:
    # Ownership is security-sensitive and intentionally cannot be discarded
    # automatically: doing so would make private portfolios globally visible.
    raise RuntimeError("Downgrading would remove portfolio ownership protection.")

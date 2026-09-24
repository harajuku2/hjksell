"""Keep unbound Telegram channel discovery inside its portfolio."""

from alembic import op
import sqlalchemy as sa


revision = "0011_portfolio_scoped_discovered_channels"
down_revision = "0010_telegram_portfolio_owners"
branch_labels = None
depends_on = None


def upgrade() -> None:
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("telegram_channels")}
    if "is_bound" in columns:
        return
    op.add_column(
        "telegram_channels",
        sa.Column("is_bound", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.execute("UPDATE telegram_channels SET is_bound = 0 WHERE portfolio_id IS NULL")


def downgrade() -> None:
    raise RuntimeError("Downgrading would merge portfolio-scoped Telegram channel discoveries.")

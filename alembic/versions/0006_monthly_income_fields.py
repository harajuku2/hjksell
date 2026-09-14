"""Add monthly other income and advertising values."""

from alembic import op
import sqlalchemy as sa

revision = "0006_monthly_income_fields"
down_revision = "0005_portfolio_telegram_configs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "monthly_expenses",
        sa.Column("other_income_byn", sa.Numeric(12, 2), nullable=False, server_default=sa.text("0")),
    )
    op.add_column(
        "monthly_expenses",
        sa.Column("advertising_byn", sa.Numeric(12, 2), nullable=False, server_default=sa.text("0")),
    )


def downgrade() -> None:
    op.drop_column("monthly_expenses", "advertising_byn")
    op.drop_column("monthly_expenses", "other_income_byn")

"""Add portfolio defaults for automatic per-item purchase expenses."""

from alembic import op
import sqlalchemy as sa


revision = "0009_portfolio_automatic_expense"
down_revision = "0008_item_purchase_expense"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("portfolio_currency_settings")}
    if "automatic_expense_amount" not in columns:
        op.add_column(
            "portfolio_currency_settings",
            sa.Column("automatic_expense_amount", sa.Numeric(12, 2), nullable=False, server_default="0.00"),
        )
    if "automatic_expense_currency" not in columns:
        op.add_column(
            "portfolio_currency_settings",
            sa.Column("automatic_expense_currency", sa.String(length=3), nullable=False, server_default="PLN"),
        )
        op.execute(
            "UPDATE portfolio_currency_settings "
            "SET automatic_expense_currency = purchase_currency"
        )
    if "automatic_expense_purchase_rate" not in columns:
        op.add_column(
            "portfolio_currency_settings",
            sa.Column(
                "automatic_expense_purchase_rate",
                sa.Numeric(14, 6),
                nullable=False,
                server_default="1.0000",
            ),
        )


def downgrade() -> None:
    op.drop_column("portfolio_currency_settings", "automatic_expense_purchase_rate")
    op.drop_column("portfolio_currency_settings", "automatic_expense_currency")
    op.drop_column("portfolio_currency_settings", "automatic_expense_amount")

"""Add portfolio currency profiles and historical item currency codes."""

from alembic import op
import sqlalchemy as sa


revision = "0007_portfolio_currencies"
down_revision = "0006_monthly_income_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    item_columns = {column["name"] for column in inspector.get_columns("items")}
    if "purchase_currency" not in item_columns:
        op.add_column(
            "items",
            sa.Column("purchase_currency", sa.String(length=3), nullable=False, server_default="PLN"),
        )
    if "sale_currency" not in item_columns:
        op.add_column(
            "items",
            sa.Column("sale_currency", sa.String(length=3), nullable=False, server_default="BYN"),
        )
    if not inspector.has_table("portfolio_currency_settings"):
        op.create_table(
            "portfolio_currency_settings",
            sa.Column("portfolio_id", sa.Integer(), nullable=False),
            sa.Column("purchase_currency", sa.String(length=3), nullable=False, server_default="PLN"),
            sa.Column("sale_currency", sa.String(length=3), nullable=False, server_default="BYN"),
            sa.Column("exchange_rate", sa.Numeric(14, 6), nullable=False, server_default="0.8500"),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.func.current_timestamp(), nullable=False),
            sa.ForeignKeyConstraint(["portfolio_id"], ["portfolios.id"]),
            sa.PrimaryKeyConstraint("portfolio_id"),
        )


def downgrade() -> None:
    op.drop_table("portfolio_currency_settings")
    op.drop_column("items", "sale_currency")
    op.drop_column("items", "purchase_currency")

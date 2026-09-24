"""Add item-level purchase expenses in the historical purchase currency."""

from alembic import op
import sqlalchemy as sa


revision = "0008_item_purchase_expense"
down_revision = "0007_portfolio_currencies"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("items")}
    if "purchase_expense" not in columns:
        op.add_column(
            "items",
            sa.Column("purchase_expense", sa.Numeric(12, 2), nullable=False, server_default="0.00"),
        )


def downgrade() -> None:
    op.drop_column("items", "purchase_expense")

"""Allow storing discovered Telegram channels before portfolio binding."""

from alembic import op
import sqlalchemy as sa

revision = "0004_discovered_telegram_channels"
down_revision = "0003_telegram_import_diagnostics"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("telegram_channels") as batch:
        batch.alter_column("portfolio_id", existing_type=sa.Integer(), nullable=True)


def downgrade() -> None:
    with op.batch_alter_table("telegram_channels") as batch:
        batch.alter_column("portfolio_id", existing_type=sa.Integer(), nullable=False)

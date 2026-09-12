"""Store Telegram import diagnostics without deleting existing records."""

from alembic import op
import sqlalchemy as sa

revision = "0003_telegram_import_diagnostics"
down_revision = "0002_telegram_dedup_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("telegram_imports") as batch:
        batch.alter_column("channel_id", existing_type=sa.String(length=128), nullable=True)
        batch.alter_column("message_id", existing_type=sa.Integer(), nullable=True)
        batch.add_column(sa.Column("status", sa.String(length=16), nullable=False, server_default="imported"))
        batch.add_column(sa.Column("error_message", sa.String(length=512), nullable=True))
        batch.add_column(sa.Column("processed_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("telegram_imports") as batch:
        batch.drop_column("processed_at")
        batch.drop_column("error_message")
        batch.drop_column("status")
        batch.alter_column("message_id", existing_type=sa.Integer(), nullable=False)
        batch.alter_column("channel_id", existing_type=sa.String(length=128), nullable=False)

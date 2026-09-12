"""Stage 4 Telegram duplicate protection.

Revision ID: 0002_telegram_dedup_indexes
"""

from alembic import op
from sqlalchemy import inspect, text

revision = "0002_telegram_dedup_indexes"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Remove legacy duplicates, then enforce both Telegram dedupe keys."""

    bind = op.get_bind()
    # Never delete import history during an application upgrade. Fresh databases
    # receive both indexes; legacy databases with duplicates remain protected by
    # TelegramRepository.has_import until their history is reviewed.
    duplicate_channel_messages = bind.execute(
        text(
            "SELECT COUNT(*) FROM (SELECT channel_id, message_id FROM telegram_imports "
            "GROUP BY channel_id, message_id HAVING COUNT(*) > 1)"
        )
    ).scalar_one()
    duplicate_updates = bind.execute(
        text(
            "SELECT COUNT(*) FROM (SELECT update_id FROM telegram_imports "
            "GROUP BY update_id HAVING COUNT(*) > 1)"
        )
    ).scalar_one()
    existing = {index["name"] for index in inspect(bind).get_indexes("telegram_imports")}
    if not duplicate_channel_messages and "uq_telegram_import_channel_message" not in existing:
        op.create_index(
            "uq_telegram_import_channel_message",
            "telegram_imports",
            ["channel_id", "message_id"],
            unique=True,
        )
    if not duplicate_updates and "uq_telegram_import_update" not in existing:
        op.create_index("uq_telegram_import_update", "telegram_imports", ["update_id"], unique=True)


def downgrade() -> None:
    op.drop_index("uq_telegram_import_update", table_name="telegram_imports")
    op.drop_index("uq_telegram_import_channel_message", table_name="telegram_imports")

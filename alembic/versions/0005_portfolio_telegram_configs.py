"""Separate Telegram credentials, offsets, and import identity by portfolio."""

from alembic import op
import sqlalchemy as sa

revision = "0005_portfolio_telegram_configs"
down_revision = "0004_discovered_telegram_channels"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table(
        "telegram_channels",
        recreate="always",
        table_args=(sa.UniqueConstraint("portfolio_id", "channel_id", name="uq_telegram_channel_portfolio"),),
    ):
        pass
    op.create_table(
        "telegram_configs",
        sa.Column("portfolio_id", sa.Integer(), sa.ForeignKey("portfolios.id"), primary_key=True),
        sa.Column("token", sa.String(length=2048), nullable=True),
        sa.Column("update_offset", sa.Integer(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )
    op.add_column("telegram_imports", sa.Column("portfolio_id", sa.Integer(), nullable=True))
    op.drop_index("uq_telegram_import_channel_message", table_name="telegram_imports")
    op.drop_index("uq_telegram_import_update", table_name="telegram_imports")
    op.create_index(
        "uq_telegram_import_portfolio_channel_message",
        "telegram_imports",
        ["portfolio_id", "channel_id", "message_id"],
        unique=True,
    )
    op.create_index(
        "uq_telegram_import_portfolio_update",
        "telegram_imports",
        ["portfolio_id", "update_id"],
        unique=True,
    )

    bind = op.get_bind()
    bind.execute(
        sa.text(
            "UPDATE telegram_imports SET portfolio_id = ("
            "SELECT portfolio_id FROM telegram_channels "
            "WHERE telegram_channels.channel_id = telegram_imports.channel_id "
            "AND telegram_channels.portfolio_id IS NOT NULL LIMIT 1)"
            "WHERE portfolio_id IS NULL"
        )
    )
    portfolios = bind.execute(sa.text("SELECT id FROM portfolios ORDER BY id")).fetchall()
    legacy_token = bind.execute(
        sa.text("SELECT value FROM settings WHERE key = 'telegram_bot_token'")
    ).scalar_one_or_none()
    legacy_offset = bind.execute(
        sa.text("SELECT value FROM settings WHERE key = 'telegram_update_offset'")
    ).scalar_one_or_none()
    channels = bind.execute(
        sa.text("SELECT DISTINCT portfolio_id FROM telegram_channels WHERE portfolio_id IS NOT NULL")
    ).fetchall()
    channel_portfolios = [int(row[0]) for row in channels]
    if legacy_token and len(channel_portfolios) == 1:
        portfolio_id = channel_portfolios[0]
        bind.execute(
            sa.text(
                "INSERT INTO telegram_configs (portfolio_id, token, update_offset) "
                "VALUES (:portfolio_id, :token, :offset)"
            ),
            {"portfolio_id": portfolio_id, "token": legacy_token, "offset": int(legacy_offset) if legacy_offset else None},
        )
    else:
        bind.execute(
            sa.text("INSERT INTO telegram_configs (portfolio_id) VALUES (:portfolio_id)"),
            [{"portfolio_id": int(row[0])} for row in portfolios],
        )


def downgrade() -> None:
    op.drop_index("uq_telegram_import_portfolio_update", table_name="telegram_imports")
    op.drop_index("uq_telegram_import_portfolio_channel_message", table_name="telegram_imports")
    op.drop_column("telegram_imports", "portfolio_id")
    op.drop_table("telegram_configs")

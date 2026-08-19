"""app.notify_channel 消息推送渠道表。"""

from alembic import op

revision = "012_notify_channel"
down_revision = "011_drop_trading_plans"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS app.notify_channel (
          id uuid PRIMARY KEY,
          user_id uuid NOT NULL,
          channel_type text NOT NULL DEFAULT 'feishu',
          name text NOT NULL,
          config_json text NOT NULL DEFAULT '{}',
          enabled boolean NOT NULL DEFAULT TRUE,
          created_at text NOT NULL,
          updated_at text NOT NULL
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_notify_channel_user ON app.notify_channel (user_id)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS app.notify_channel")

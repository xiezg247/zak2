"""app.auto_schedule 自动任务表。"""

from alembic import op

revision = "013_auto_schedule"
down_revision = "012_notify_channel"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS app.auto_schedule (
          id bigserial PRIMARY KEY,
          user_id uuid NOT NULL,
          name varchar(64) NOT NULL,
          recipe_id varchar(64) NOT NULL,
          days_of_week text NOT NULL,
          times jsonb NOT NULL DEFAULT '[]',
          enabled boolean NOT NULL DEFAULT TRUE,
          last_run_at text,
          last_message text,
          last_success boolean,
          created_at text NOT NULL,
          updated_at text NOT NULL
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_auto_schedule_user ON app.auto_schedule (user_id)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS app.auto_schedule")

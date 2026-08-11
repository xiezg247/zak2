"""app.web_team_reports（原运行时旁路建表）。"""

from alembic import op

revision = "007_web_team_reports"
down_revision = "006_dbbardata_perf_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS app.web_team_reports (
          id bigserial PRIMARY KEY,
          user_id uuid NOT NULL,
          symbol text NOT NULL,
          exchange text NOT NULL,
          vt_symbol text NOT NULL DEFAULT '',
          title text NOT NULL DEFAULT '',
          body text NOT NULL,
          summary text NOT NULL DEFAULT '',
          mode text NOT NULL DEFAULT 'fast',
          context_json text NOT NULL DEFAULT '',
          created_at text NOT NULL
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_web_team_reports_user_vt
        ON app.web_team_reports (user_id, vt_symbol, created_at DESC)
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS app.web_team_reports")

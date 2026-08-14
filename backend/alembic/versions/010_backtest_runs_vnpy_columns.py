"""backtest_runs vnpy columns"""

from __future__ import annotations

from alembic import op

revision = "010_backtest_runs_vnpy_columns"
down_revision = "009_create_public_bars"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE app.backtest_runs ADD COLUMN IF NOT EXISTS engine TEXT")
    op.execute(
        "ALTER TABLE app.backtest_runs ADD COLUMN IF NOT EXISTS params_json TEXT NOT NULL DEFAULT '{}'"
    )
    op.execute(
        "ALTER TABLE app.backtest_runs ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'success'"
    )
    op.execute("ALTER TABLE app.backtest_runs ADD COLUMN IF NOT EXISTS error_message TEXT")


def downgrade() -> None:
    op.execute("ALTER TABLE app.backtest_runs DROP COLUMN IF EXISTS error_message")
    op.execute("ALTER TABLE app.backtest_runs DROP COLUMN IF EXISTS status")
    op.execute("ALTER TABLE app.backtest_runs DROP COLUMN IF EXISTS params_json")
    op.execute("ALTER TABLE app.backtest_runs DROP COLUMN IF EXISTS engine")

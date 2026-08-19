"""移除交易计划：trading_plans / trading_plan_symbols 表与 watchlist_positions.plan_pct"""

from __future__ import annotations

from alembic import op

revision = "011_drop_trading_plans"
down_revision = "010_backtest_runs_vnpy_columns"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DROP TABLE IF EXISTS app.trading_plan_symbols")
    op.execute("DROP TABLE IF EXISTS app.trading_plans")
    op.execute("ALTER TABLE app.watchlist_positions DROP COLUMN IF EXISTS plan_pct")


def downgrade() -> None:
    op.execute("ALTER TABLE app.watchlist_positions ADD COLUMN IF NOT EXISTS plan_pct DOUBLE PRECISION")

"""app.stock_industry 与 app.limit_list_daily（原运行时旁路建表）。"""

from alembic import op

revision = "008_stock_industry_limit_list"
down_revision = "007_web_team_reports"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS app.stock_industry (
          symbol text NOT NULL,
          exchange text NOT NULL,
          industry text NOT NULL DEFAULT '',
          industry_l1 text NOT NULL DEFAULT '',
          source text NOT NULL DEFAULT '',
          updated_at text NOT NULL DEFAULT '',
          PRIMARY KEY (symbol, exchange)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS app.limit_list_daily (
          trade_date text NOT NULL,
          vt_symbol text NOT NULL,
          ts_code text NOT NULL DEFAULT '',
          name text NOT NULL DEFAULT '',
          limit_times double precision NOT NULL DEFAULT 0,
          first_time text NOT NULL DEFAULT '',
          last_time text NOT NULL DEFAULT '',
          fd_amount double precision NOT NULL DEFAULT 0,
          open_times double precision NOT NULL DEFAULT 0,
          strth double precision NOT NULL DEFAULT 0,
          updated_at text NOT NULL DEFAULT '',
          PRIMARY KEY (trade_date, vt_symbol)
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS app.limit_list_daily")
    op.execute("DROP TABLE IF EXISTS app.stock_industry")

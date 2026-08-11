"""从旧 zak PG 一次性导入到 zak2（truncate-then-copy）。"""

from __future__ import annotations

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

# 子表在前，父表在后（truncate CASCADE 时按此顺序亦可统一 CASCADE）
DEFAULT_COPY_TABLES: list[str] = [
    "auth.users",
    "auth.user_preferences",
    "app.watchlist",
    "app.watchlist_groups",
    "app.watchlist_group_members",
    "app.watchlist_positions",
    "app.screener_schemes",
    "app.screener_recipes",
    "app.screener_runs",
    "app.trading_playbook_sections",
    "app.trading_playbook_discipline_daily",
    "app.stock_note_memos",
    "app.stock_note_entries",
    "app.feed_subscriptions",
    "app.feed_items",
    "app.feed_item_reads",
    "app.trading_plans",
    "app.trading_plan_symbols",
    "app.notify_delivery_log",
    "app.backtest_runs",
    "app.web_team_reports",
    "chat.sessions",
    "chat.messages",
]

MARKET_SYNC_TABLES: list[str] = [
    "app.meta",
    "app.universe",
    "app.stock_industry",
    "app.trade_calendar",
    "app.limit_list_daily",
    "app.sector_flow_daily",
    "app.sector_flow_intraday",
    "app.emotion_limit_ladder_daily",
]


def tables_for_import(*, with_market_sync: bool) -> list[str]:
    out = list(DEFAULT_COPY_TABLES)
    if with_market_sync:
        out.extend(MARKET_SYNC_TABLES)
    return out


def _eng(url: str) -> Engine:
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    return create_engine(url, pool_pre_ping=True)


def target_has_rows(engine: Engine, table: str) -> bool:
    with engine.connect() as conn:
        return bool(conn.execute(text(f"SELECT 1 FROM {table} LIMIT 1")).first())


def import_tables(
    source_url: str,
    target_url: str,
    tables: list[str],
    *,
    force: bool,
) -> dict[str, int]:
    src = _eng(source_url)
    dst = _eng(target_url)
    counts: dict[str, int] = {}
    if not force:
        for t in tables:
            if target_has_rows(dst, t):
                raise RuntimeError(f"目标表非空：{t}；请传 --force 或清空后再导")
    with dst.begin() as conn:
        for t in tables:
            conn.execute(text(f"TRUNCATE {t} CASCADE"))
    with src.connect() as sconn, dst.begin() as dconn:
        for t in tables:
            rows = sconn.execute(text(f"SELECT * FROM {t}")).mappings().all()
            if not rows:
                counts[t] = 0
                continue
            cols = list(rows[0].keys())
            col_list = ", ".join(cols)
            placeholders = ", ".join(f":{c}" for c in cols)
            dconn.execute(
                text(f"INSERT INTO {t} ({col_list}) VALUES ({placeholders})"),
                [dict(r) for r in rows],
            )
            counts[t] = len(rows)
    return counts

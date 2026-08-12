"""关注池 1m：薄盘点（不下载）。"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.ops_bars_fill import list_watchlist_symbols
from app.services.ops_scheduler import save_job_run_meta
from app.services.symbols import normalize_exchange

JOB_ID = "fill_focus_pool_minute"
POOL_CAP = 500


def _count_overview(
    db: Session,
    pool: list[tuple[str, str]],
    *,
    interval: str,
) -> int:
    if not pool:
        return 0
    syms = [s for s, _ in pool]
    exchs = [normalize_exchange(e) for _, e in pool]
    row = db.execute(
        text(
            """
            SELECT COUNT(*)::int AS n
            FROM public.dbbaroverview o
            WHERE o.interval = :iv
              AND EXISTS (
                SELECT 1
                FROM unnest(CAST(:syms AS text[]), CAST(:exchs AS text[])) AS p(symbol, exchange)
                WHERE p.symbol = o.symbol AND p.exchange = o.exchange
              )
            """
        ),
        {"iv": interval, "syms": syms, "exchs": exchs},
    ).mappings().first()
    return int((row or {}).get("n") or 0)


def fill_focus_pool_minute(db: Session) -> dict[str, Any]:
    raw = list_watchlist_symbols(db)
    truncated = len(raw) > POOL_CAP
    pool = raw[:POOL_CAP]
    pool_size = len(pool)
    with_daily = _count_overview(db, pool, interval="d") if pool_size else 0
    with_1m = _count_overview(db, pool, interval="1m") if pool_size else 0
    missing_1m = pool_size - with_1m
    msg = (
        f"1m 下载未接入，本跑仅盘点：pool={pool_size} daily={with_daily} "
        f"1m={with_1m} missing_1m={missing_1m}"
    )
    if truncated:
        msg += f"（已截断至 {POOL_CAP}）"
    save_job_run_meta(db, JOB_ID, last_message=msg, last_success=True)
    return {
        "success": True,
        "skipped": False,
        "pool_size": pool_size,
        "with_daily": with_daily,
        "with_1m": with_1m,
        "missing_1m": missing_1m,
        "message": msg,
    }

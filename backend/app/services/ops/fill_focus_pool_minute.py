"""关注池 1m：自选池增量下载。"""

from __future__ import annotations

import os
import time
from datetime import date, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services import bar_download as bars
from app.services import tushare_client as ts
from app.services.bar_download import INTERVAL_1M, download_minute_bars, get_overview_row
from app.services.ops.bars_fill import list_watchlist_symbols
from app.services.ops.scheduler import save_job_run_meta
from app.services.ops.sync_sector import recent_open_dates
from app.services.symbols import normalize_exchange

JOB_ID = "fill_focus_pool_minute"


def _lookback_days() -> int:
    raw = os.getenv("FOCUS_1M_LOOKBACK_DAYS", "5").strip()
    try:
        return max(1, min(int(raw), 20))
    except ValueError:
        return 5


def _max_symbols() -> int:
    raw = os.getenv("FOCUS_1M_MAX_SYMBOLS", "50").strip()
    try:
        return max(1, min(int(raw), 500))
    except ValueError:
        return 50


def _sleep() -> None:
    raw = os.getenv("BARS_FILL_SLEEP_SEC", "0.05").strip()
    try:
        sec = max(0.0, min(float(raw), 2.0))
    except ValueError:
        sec = 0.05
    if sec > 0:
        time.sleep(sec)


def _yyyymmdd_to_date(ymd: str) -> date:
    return datetime.strptime(ymd[:8], "%Y%m%d").date()


def _open_date_window(db: Session) -> tuple[date, date]:
    ymds = recent_open_dates(db, lookback=_lookback_days())
    dates = [_yyyymmdd_to_date(y) for y in ymds if y]
    if not dates:
        today = date.today()
        return today, today
    return min(dates), max(dates)


def _needs_1m_download(
    db: Session,
    symbol: str,
    exchange: str,
    *,
    as_of: date,
) -> bool:
    row = get_overview_row(db, symbol=symbol, exchange=exchange, interval=INTERVAL_1M)
    if not row:
        return True
    return bars.is_stale_end(row.get("end"), as_of=as_of)


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
    row = (
        db.execute(
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
        )
        .mappings()
        .first()
    )
    if row is None:
        return 0
    return int(row["n"] or 0)


def _empty_result(
    *,
    success: bool,
    skipped: bool,
    message: str,
    pool_size: int = 0,
    lookback_days: int | None = None,
    max_symbols: int | None = None,
) -> dict[str, Any]:
    return {
        "success": success,
        "skipped": skipped,
        "pool_size": pool_size,
        "downloaded": 0,
        "bars_added": 0,
        "failed": [],
        "with_daily": 0,
        "with_1m": 0,
        "missing_1m": 0,
        "lookback_days": lookback_days if lookback_days is not None else _lookback_days(),
        "max_symbols": max_symbols if max_symbols is not None else _max_symbols(),
        "message": message,
    }


def fill_focus_pool_minute(db: Session) -> dict[str, Any]:
    lookback = _lookback_days()
    max_n = _max_symbols()
    try:
        ts.require_token()
    except ts.TushareNotConfiguredError as exc:
        msg = str(exc)
        save_job_run_meta(db, JOB_ID, last_message=msg, last_success=False)
        return _empty_result(
            success=False,
            skipped=True,
            message=msg,
            lookback_days=lookback,
            max_symbols=max_n,
        )

    pool = list_watchlist_symbols(db)[:max_n]
    if not pool:
        msg = f"关注池 1m：pool=0 downloaded=0 bars=0 failed=0 lookback={lookback} daily=0 1m=0 missing_1m=0"
        save_job_run_meta(db, JOB_ID, last_message=msg, last_success=True)
        return _empty_result(
            success=True,
            skipped=False,
            message=msg,
            pool_size=0,
            lookback_days=lookback,
            max_symbols=max_n,
        )

    start_d, end_d = _open_date_window(db)
    as_of = end_d
    downloaded = 0
    bars_added = 0
    failed: list[str] = []
    for symbol, exchange in pool:
        if not _needs_1m_download(db, symbol, exchange, as_of=as_of):
            continue
        try:
            n = download_minute_bars(db, symbol=symbol, exchange=exchange, start=start_d, end=end_d)
            db.commit()
            downloaded += 1
            bars_added += n
        except Exception as exc:
            db.rollback()
            failed.append(f"{symbol}.{exchange}:{exc}")
        _sleep()

    with_daily = _count_overview(db, pool, interval="d")
    with_1m = _count_overview(db, pool, interval="1m")
    missing_1m = len(pool) - with_1m
    msg = (
        f"关注池 1m：pool={len(pool)} downloaded={downloaded} bars={bars_added} "
        f"failed={len(failed)} lookback={lookback} "
        f"daily={with_daily} 1m={with_1m} missing_1m={missing_1m}"
    )
    save_job_run_meta(db, JOB_ID, last_message=msg, last_success=True)
    return {
        "success": True,
        "skipped": False,
        "pool_size": len(pool),
        "downloaded": downloaded,
        "bars_added": bars_added,
        "failed": failed,
        "with_daily": with_daily,
        "with_1m": with_1m,
        "missing_1m": missing_1m,
        "lookback_days": lookback,
        "max_symbols": max_n,
        "message": msg,
    }

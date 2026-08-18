"""日 K 补全 job：自选 + 全市场过期。"""

from __future__ import annotations

import os
import time
from datetime import date

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.schemas.ops import SyncResult
from app.services.market import bar_download as bars
from app.services.market import tushare_client as ts
from app.services.ops.scheduler import save_job_run_meta
from app.services.symbols import normalize_exchange

JOB_WATCHLIST = "fill_watchlist_bars"
JOB_STALE = "batch_fill_stale"
JOB_UNIVERSE = "batch_download_universe"


def _max_symbols() -> int:
    raw = os.getenv("BARS_FILL_MAX_SYMBOLS", "500").strip()
    try:
        return max(1, min(int(raw), 5000))
    except ValueError:
        return 500


def _sleep_sec() -> float:
    raw = os.getenv("BARS_FILL_SLEEP_SEC", "0.05").strip()
    try:
        return max(0.0, min(float(raw), 2.0))
    except ValueError:
        return 0.05


def list_watchlist_symbols(db: Session) -> list[tuple[str, str]]:
    rows = (
        db.execute(
            text(
                """
            SELECT DISTINCT symbol, exchange
            FROM app.watchlist
            WHERE symbol IS NOT NULL AND exchange IS NOT NULL
            ORDER BY exchange, symbol
            """
            )
        )
        .mappings()
        .all()
    )
    return [(str(r["symbol"]), normalize_exchange(str(r["exchange"]))) for r in rows]


def _fill_one(db: Session, *, symbol: str, exchange: str, as_of: date) -> tuple[str, int]:
    """返回 (status, bars_added)：ok|skip|fail。"""
    rng = bars.resolve_fill_range(db, symbol=symbol, exchange=exchange, as_of=as_of)
    if rng is None:
        return "skip", 0
    start, end = rng
    try:
        n = bars.download_daily_bars(db, symbol=symbol, exchange=exchange, start=start, end=end)
        db.commit()
        return ("ok" if n > 0 else "skip"), n
    except Exception:
        db.rollback()
        return "fail", 0


def _run_pool(db: Session, pool: list[tuple[str, str]], *, job_id: str) -> SyncResult:
    try:
        ts.require_token()
    except ts.TushareNotConfiguredError as exc:
        message = str(exc)
        save_job_run_meta(db, job_id, last_message=message, last_success=False)
        return SyncResult(
            success=False,
            message=message,
            extra={
                "attempted": 0,
                "success_count": 0,
                "failed": [],
                "bars_added": 0,
                "up_to_date": 0,
            },
        )

    as_of = bars.as_of_trade_date(db)
    sleep_sec = _sleep_sec()
    attempted = 0
    success_count = 0
    up_to_date = 0
    bars_added = 0
    failed: list[str] = []

    for symbol, exchange in pool:
        attempted += 1
        status, n = _fill_one(db, symbol=symbol, exchange=exchange, as_of=as_of)
        label = f"{symbol}.{exchange}"
        if status == "ok":
            success_count += 1
            bars_added += n
        elif status == "skip":
            up_to_date += 1
        else:
            failed.append(label)
        if sleep_sec > 0:
            time.sleep(sleep_sec)

    if attempted == 0:
        message = "没有需要补全的标的"
    else:
        message = (
            f"补全完成：成功 {success_count}/{attempted}，新增 {bars_added} 根，已最新 {up_to_date}，失败 {len(failed)}"
        )
    success = len(failed) == 0 or success_count > 0 or up_to_date == attempted
    # 全失败且有 attempted → success False
    if attempted and success_count == 0 and up_to_date == 0 and failed:
        success = False
    save_job_run_meta(db, job_id, last_message=message[:500], last_success=success)
    return SyncResult(
        success=success,
        message=message,
        extra={
            "attempted": attempted,
            "success_count": success_count,
            "failed": failed[:50],
            "bars_added": bars_added,
            "up_to_date": up_to_date,
            "as_of": as_of.isoformat(),
        },
    )


def fill_watchlist_bars(db: Session) -> SyncResult:
    pool = list_watchlist_symbols(db)
    return _run_pool(db, pool, job_id=JOB_WATCHLIST)


def batch_fill_stale(db: Session) -> SyncResult:
    as_of = bars.as_of_trade_date(db)
    stale = bars.list_stale_overviews(db, as_of=as_of, limit=_max_symbols())
    pool = [(s, e) for s, e, _ in stale]
    return _run_pool(db, pool, job_id=JOB_STALE)


def _is_missing_overview(sym_ex: tuple[str, str], starts: dict[tuple[str, str], date | None]) -> bool:
    return sym_ex not in starts or starts.get(sym_ex) is None


def _load_overview_starts(db: Session) -> dict[tuple[str, str], date | None]:
    rows = (
        db.execute(
            text(
                """
            SELECT symbol, exchange, start
            FROM public.dbbaroverview
            WHERE interval = 'd'
            """
            )
        )
        .mappings()
        .all()
    )
    return {
        (str(r["symbol"]), normalize_exchange(str(r["exchange"]))): bars.overview_end_date(r["start"]) for r in rows
    }


def _download_universe_one(
    db: Session,
    *,
    symbol: str,
    exchange: str,
    unified_start: date,
    as_of: date,
) -> tuple[str, int]:
    """返回 (status, bars_added)：ok|skip|fail。"""
    try:
        n = bars.download_daily_bars(db, symbol=symbol, exchange=exchange, start=unified_start, end=as_of)
        db.commit()
        return ("ok" if n > 0 else "skip"), n
    except Exception:
        db.rollback()
        return "fail", 0


def batch_download_universe(db: Session) -> SyncResult:
    try:
        ts.require_token()
    except ts.TushareNotConfiguredError as exc:
        message = str(exc)
        save_job_run_meta(db, JOB_UNIVERSE, last_message=message, last_success=False)
        return SyncResult(
            success=False,
            message=message,
            extra={
                "attempted": 0,
                "success_count": 0,
                "failed": [],
                "bars_added": 0,
                "up_to_date": 0,
                "skipped_covered": 0,
            },
        )

    universe = bars.list_universe_symbols(db)
    if not universe:
        message = "全 A 股列表为空，请先同步 A 股列表"
        save_job_run_meta(db, JOB_UNIVERSE, last_message=message, last_success=False)
        return SyncResult(
            success=False,
            message=message,
            extra={
                "attempted": 0,
                "success_count": 0,
                "failed": [],
                "bars_added": 0,
                "up_to_date": 0,
                "skipped_covered": 0,
            },
        )

    unified = bars.parse_universe_start(None)
    as_of = bars.as_of_trade_date(db)
    starts = _load_overview_starts(db)
    targets = bars.select_universe_daily_targets(universe, starts, unified_start=unified)
    missing = [t for t in targets if _is_missing_overview(t, starts)]
    backfill = [t for t in targets if not _is_missing_overview(t, starts)]
    targets = missing + backfill
    skipped_covered = len(universe) - len(targets)
    max_syms = _max_symbols()
    pool = targets[:max_syms]
    remaining = len(targets) - len(pool)

    sleep_sec = _sleep_sec()
    attempted = 0
    success_count = 0
    no_data = 0
    bars_added = 0
    failed: list[str] = []

    for symbol, exchange in pool:
        attempted += 1
        status, n = _download_universe_one(db, symbol=symbol, exchange=exchange, unified_start=unified, as_of=as_of)
        label = f"{symbol}.{exchange}"
        if status == "ok":
            success_count += 1
            bars_added += n
        elif status == "skip":
            no_data += 1
        else:
            failed.append(label)
        if sleep_sec > 0:
            time.sleep(sleep_sec)

    if attempted == 0:
        message = f"全市场日 K 均已覆盖（跳过 {skipped_covered}）"
    else:
        message = (
            f"全市场日 K 下载完成：成功 {success_count}/{attempted}，新增 {bars_added} 根，"
            f"无数据 {no_data}，失败 {len(failed)}，已覆盖跳过 {skipped_covered}"
        )
        if remaining > 0:
            message += f"；尚余 {remaining} 只下次继续"
    success = len(failed) == 0 or success_count > 0 or no_data == attempted
    if attempted and success_count == 0 and no_data == 0 and failed:
        success = False
    save_job_run_meta(db, JOB_UNIVERSE, last_message=message[:500], last_success=success)
    return SyncResult(
        success=success,
        message=message,
        extra={
            "attempted": attempted,
            "success_count": success_count,
            "failed": failed[:50],
            "bars_added": bars_added,
            "up_to_date": skipped_covered,
            "skipped_covered": skipped_covered,
            "as_of": as_of.isoformat(),
        },
    )

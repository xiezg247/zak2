"""同步涨停列表（Tushare limit_list_d → app.limit_list_daily）。"""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.time import china_today
from app.services import tushare_client as ts
from app.services.ops.scheduler import save_job_run_meta
from app.services.tushare_screener import latest_open_yyyymmdd, ts_code_to_tf

JOB_ID = "sync_limit_list"

_FIELDS = "ts_code,trade_date,name,limit_times,first_time,last_time,fd_amount,open_times,strth"


def _lookback_days() -> int:
    raw = os.getenv("LIMIT_LIST_SYNC_DAYS", "1").strip()
    try:
        return max(1, min(int(raw), 5))
    except ValueError:
        return 1


def _to_yyyymmdd(cal_date: str) -> str:
    return cal_date.replace("-", "")[:8]


def recent_open_dates(db: Session, *, lookback: int) -> list[str]:
    rows = db.execute(
        text(
            """
            SELECT cal_date
            FROM app.trade_calendar
            WHERE is_open = 1 AND cal_date <= CURRENT_DATE::text
            ORDER BY cal_date DESC
            LIMIT :n
            """
        ),
        {"n": lookback},
    ).scalars()
    dates = [_to_yyyymmdd(str(d)) for d in rows if d]
    if dates:
        return dates
    out: list[str] = []
    day = china_today()
    while len(out) < lookback:
        if day.weekday() < 5:
            out.append(day.strftime("%Y%m%d"))
        day -= timedelta(days=1)
    return out


def _now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _upsert_row(
    db: Session,
    *,
    trade_date: str,
    vt_symbol: str,
    ts_code: str,
    name: str,
    limit_times: float,
    first_time: str,
    last_time: str,
    fd_amount: float,
    open_times: float,
    strth: float,
    updated_at: str,
) -> None:
    db.execute(
        text(
            """
            INSERT INTO app.limit_list_daily
                (trade_date, vt_symbol, ts_code, name, limit_times,
                 first_time, last_time, fd_amount, open_times, strth, updated_at)
            VALUES
                (:td, :vt, :ts, :name, :lt,
                 :ft, :ltm, :fd, :ot, :strth, :upd)
            ON CONFLICT (trade_date, vt_symbol) DO UPDATE SET
                ts_code = EXCLUDED.ts_code,
                name = EXCLUDED.name,
                limit_times = EXCLUDED.limit_times,
                first_time = EXCLUDED.first_time,
                last_time = EXCLUDED.last_time,
                fd_amount = EXCLUDED.fd_amount,
                open_times = EXCLUDED.open_times,
                strth = EXCLUDED.strth,
                updated_at = EXCLUDED.updated_at
            """
        ),
        {
            "td": trade_date,
            "vt": vt_symbol,
            "ts": ts_code,
            "name": name,
            "lt": limit_times,
            "ft": first_time,
            "ltm": last_time,
            "fd": fd_amount,
            "ot": open_times,
            "strth": strth,
            "upd": updated_at,
        },
    )


def sync_one_day(db: Session, trade_date: str) -> int:
    """拉取并 upsert 单日涨停列表；返回写入行数。"""
    td = _to_yyyymmdd(trade_date)
    rows = ts.query(
        "limit_list_d",
        {"trade_date": td, "limit_type": "U"},
        fields=_FIELDS,
    )
    updated_at = _now_iso()
    count = 0
    for row in rows:
        ts_code = str(row.get("ts_code") or "").strip()
        if not ts_code:
            continue
        vt_symbol = ts_code_to_tf(ts_code)
        if not vt_symbol:
            continue
        row_td = _to_yyyymmdd(str(row.get("trade_date") or td))
        _upsert_row(
            db,
            trade_date=row_td or td,
            vt_symbol=vt_symbol,
            ts_code=ts_code,
            name=str(row.get("name") or "").strip(),
            limit_times=ts.safe_float(row.get("limit_times")),
            first_time=str(row.get("first_time") or "").strip(),
            last_time=str(row.get("last_time") or "").strip(),
            fd_amount=ts.safe_float(row.get("fd_amount")),
            open_times=ts.safe_float(row.get("open_times")),
            strth=ts.safe_float(row.get("strth")),
            updated_at=updated_at,
        )
        count += 1
    return count


def sync_limit_list(db: Session) -> dict[str, Any]:
    try:
        ts.require_token()
    except ts.TushareNotConfiguredError as exc:
        message = str(exc)
        save_job_run_meta(db, JOB_ID, last_message=message, last_success=False)
        return {"success": False, "message": message, "days": 0, "rows": 0, "skipped": True}

    lookback = _lookback_days()
    dates = recent_open_dates(db, lookback=lookback)
    if not dates:
        dates = [latest_open_yyyymmdd(db)]

    summaries: list[str] = []
    total_rows = 0
    for trade_date in dates:
        try:
            n = sync_one_day(db, trade_date)
        except Exception as exc:
            summaries.append(f"{trade_date}:失败({exc})")
            continue
        total_rows += n
        if n:
            summaries.append(f"{trade_date}:{n}条")

    db.commit()

    if total_rows <= 0:
        message = "未同步到涨停列表（可能非交易日、Tushare 尚未更新或权限不足）"
        if summaries:
            message = "涨停列表同步失败：" + "，".join(summaries[:5])
        save_job_run_meta(db, JOB_ID, last_message=message, last_success=False)
        return {"success": False, "message": message, "days": 0, "rows": 0}

    message = "涨停列表同步 " + "，".join(summaries[:8])
    if len(summaries) > 8:
        message += f" …共{len(summaries)}日"
    save_job_run_meta(db, JOB_ID, last_message=message, last_success=True)
    return {"success": True, "message": message, "days": len(summaries), "rows": total_rows}

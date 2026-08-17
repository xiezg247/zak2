"""同步交易日历（Tushare trade_cal → app.trade_calendar）。"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.time import china_today
from app.schemas.ops import SyncResult
from app.services import tushare_client as ts
from app.services.ops.scheduler import save_job_run_meta

JOB_ID = "sync_trade_calendar"
DEFAULT_START = date(2019, 1, 1)


def _calendar_end(today: date | None = None) -> date:
    current = today or china_today()
    return date(current.year + 1, 12, 31)


def _fmt(d: date) -> str:
    return d.isoformat()


def _fmt_compact(d: date) -> str:
    return d.strftime("%Y%m%d")


def _normalize_cal_date(raw: Any) -> str:
    text_v = str(raw or "").strip()
    if len(text_v) == 8 and text_v.isdigit():
        return f"{text_v[:4]}-{text_v[4:6]}-{text_v[6:8]}"
    return text_v[:10]


def sync_trade_calendar(db: Session, *, start: date | None = None, end: date | None = None) -> SyncResult:
    start = start or DEFAULT_START
    end = end or _calendar_end()
    try:
        ts.require_token()
    except ts.TushareNotConfiguredError as exc:
        message = str(exc)
        save_job_run_meta(db, JOB_ID, last_message=message, last_success=False)
        return SyncResult(success=False, message=message, skipped=True, extra={"count": 0})

    rows = ts.query(
        "trade_cal",
        {
            "exchange": "SSE",
            "start_date": _fmt_compact(start),
            "end_date": _fmt_compact(end),
        },
        fields="cal_date,is_open",
    )
    if not rows:
        message = "交易日历同步失败（无数据）"
        save_job_run_meta(db, JOB_ID, last_message=message, last_success=False)
        return SyncResult(success=False, message=message, extra={"count": 0})

    count = 0
    for row in rows:
        cal_date = _normalize_cal_date(row.get("cal_date"))
        if not cal_date:
            continue
        is_open = int(ts.safe_float(row.get("is_open"), 0))
        db.execute(
            text(
                """
                INSERT INTO app.trade_calendar (cal_date, is_open)
                VALUES (:d, :o)
                ON CONFLICT (cal_date) DO UPDATE SET is_open = EXCLUDED.is_open
                """
            ),
            {"d": cal_date, "o": is_open},
        )
        count += 1

    for key, value in (
        ("trade_calendar_range_start", _fmt(start)),
        ("trade_calendar_range_end", _fmt(end)),
        ("trade_calendar_synced_at", datetime.now(UTC).isoformat(timespec="seconds")),
    ):
        db.execute(
            text(
                """
                INSERT INTO app.meta (key, value)
                VALUES (:k, :v)
                ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
                """
            ),
            {"k": key, "v": value},
        )
    db.commit()

    message = f"已同步交易日历 {count} 条（{_fmt(start)} ~ {_fmt(end)}）"
    save_job_run_meta(db, JOB_ID, last_message=message, last_success=True)
    return SyncResult(
        success=True,
        message=message,
        extra={"count": count, "start": _fmt(start), "end": _fmt(end)},
    )

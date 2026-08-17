"""披露日历同步：Tushare disclosure_date → app.disclosure_calendar。"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services import tushare_client as ts
from app.services.ops.scheduler import save_job_run_meta

JOB_ID = "sync_disclosure_calendar"

_FIELDS = "ts_code,end_date,pre_date,ann_date,actual_date"


def latest_report_end_yyyymmdd(today: date | None = None) -> str:
    """不晚于 today 的最近财报季末（3/6/9/12 月最后一天）。"""
    d = today or date.today()
    year = d.year
    quarter_ends = (
        date(year, 3, 31),
        date(year, 6, 30),
        date(year, 9, 30),
        date(year, 12, 31),
    )
    candidates = [q for q in quarter_ends if q <= d]
    if candidates:
        return max(candidates).strftime("%Y%m%d")
    return date(year - 1, 12, 31).strftime("%Y%m%d")


def _now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _date_field(value: Any) -> str:
    s = str(value or "").strip()
    return s.replace("-", "")[:8] if s else ""


def sync_disclosure_calendar(db: Session) -> dict[str, Any]:
    try:
        ts.require_token()
    except ts.TushareNotConfiguredError as exc:
        message = str(exc)
        save_job_run_meta(db, JOB_ID, last_message=message, last_success=False)
        return {"success": False, "skipped": True, "message": message}

    end_date = latest_report_end_yyyymmdd()
    try:
        rows = ts.query("disclosure_date", {"end_date": end_date}, fields=_FIELDS)
    except Exception as exc:  # noqa: BLE001
        message = f"disclosure_date 失败: {exc}"
        save_job_run_meta(db, JOB_ID, last_message=message[:500], last_success=False)
        return {"success": False, "skipped": True, "message": message, "end_date": end_date}

    fetched_at = _now_iso()
    payload: list[dict[str, str]] = []
    for item in rows:
        ts_code = str(item.get("ts_code") or "").strip()
        if not ts_code:
            continue
        payload.append(
            {
                "ts_code": ts_code,
                "end_date": _date_field(item.get("end_date") or end_date),
                "pre_date": _date_field(item.get("pre_date")),
                "ann_date": _date_field(item.get("ann_date")),
                "actual_date": _date_field(item.get("actual_date")),
                "fetched_at": fetched_at,
            }
        )

    if not payload:
        message = f"无披露数据（end_date={end_date}）"
        save_job_run_meta(db, JOB_ID, last_message=message, last_success=False)
        return {"success": False, "skipped": True, "message": message, "end_date": end_date}

    db.execute(
        text(
            """
            INSERT INTO app.disclosure_calendar
                (ts_code, end_date, pre_date, ann_date, actual_date, fetched_at)
            VALUES
                (:ts_code, :end_date, :pre_date, :ann_date, :actual_date, :fetched_at)
            ON CONFLICT (ts_code, end_date) DO UPDATE SET
                pre_date = EXCLUDED.pre_date,
                ann_date = EXCLUDED.ann_date,
                actual_date = EXCLUDED.actual_date,
                fetched_at = EXCLUDED.fetched_at
            """
        ),
        payload,
    )
    db.commit()
    message = f"披露日历同步 {len(payload)} 条（end_date={end_date}）"
    save_job_run_meta(db, JOB_ID, last_message=message, last_success=True)
    return {
        "success": True,
        "skipped": False,
        "message": message,
        "written": len(payload),
        "end_date": end_date,
    }

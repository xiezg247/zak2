"""Tushare 因子缓存预拉：daily_basic + moneyflow → app.tushare_factor_cache。"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services import tushare_client as ts
from app.services.ops.scheduler import save_job_run_meta
from app.services.tushare_screener import (
    fetch_daily_basic_rows,
    fetch_moneyflow_rows,
    latest_open_yyyymmdd,
)

JOB_ID = "prefetch_tushare"


def _now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _upsert_dataset(
    db: Session,
    *,
    dataset: str,
    trade_date: str,
    rows: list[dict[str, Any]],
    fetched_at: str,
) -> None:
    db.execute(
        text(
            """
            INSERT INTO app.tushare_factor_cache (dataset, trade_date, payload, fetched_at)
            VALUES (:dataset, :trade_date, :payload, :fetched_at)
            ON CONFLICT (dataset, trade_date) DO UPDATE SET
                payload = EXCLUDED.payload,
                fetched_at = EXCLUDED.fetched_at
            """
        ),
        {
            "dataset": dataset,
            "trade_date": trade_date,
            "payload": json.dumps(rows, ensure_ascii=False),
            "fetched_at": fetched_at,
        },
    )


def prefetch_tushare(db: Session) -> dict[str, Any]:
    try:
        ts.require_token()
    except ts.TushareNotConfiguredError as exc:
        message = str(exc)
        save_job_run_meta(db, JOB_ID, last_message=message, last_success=False)
        return {"success": False, "skipped": True, "message": message}

    trade_date = latest_open_yyyymmdd(db)
    notes: list[str] = []

    try:
        basic_rows = fetch_daily_basic_rows(trade_date)
    except Exception as exc:  # noqa: BLE001
        message = f"daily_basic 失败: {exc}"
        save_job_run_meta(db, JOB_ID, last_message=message[:500], last_success=False)
        return {"success": False, "skipped": True, "message": message, "trade_date": trade_date}

    if not basic_rows:
        message = f"无 daily_basic 数据（trade_date={trade_date}）"
        save_job_run_meta(db, JOB_ID, last_message=message, last_success=False)
        return {"success": False, "skipped": True, "message": message, "trade_date": trade_date}

    fetched_at = _now_iso()
    _upsert_dataset(db, dataset="daily_basic", trade_date=trade_date, rows=basic_rows, fetched_at=fetched_at)
    written = 1

    try:
        flow_rows = fetch_moneyflow_rows(trade_date)
        if flow_rows:
            _upsert_dataset(db, dataset="moneyflow", trade_date=trade_date, rows=flow_rows, fetched_at=fetched_at)
            written += 1
    except Exception as exc:  # noqa: BLE001
        notes.append(f"moneyflow 失败: {exc}")

    db.commit()
    message = f"因子缓存预拉 daily_basic {len(basic_rows)} 条（trade_date={trade_date}）"
    if notes:
        message += "；" + "；".join(notes)
    save_job_run_meta(db, JOB_ID, last_message=message, last_success=True)
    return {
        "success": True,
        "skipped": False,
        "message": message,
        "trade_date": trade_date,
        "written": written,
        "notes": notes,
    }

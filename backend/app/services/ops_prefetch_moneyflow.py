"""主力资金预拉：moneyflow → app.tushare_factor_cache。"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services import tushare_client as ts
from app.services.ops_scheduler import save_job_run_meta
from app.services.tushare_screener import fetch_moneyflow_rows, latest_open_yyyymmdd

JOB_ID = "prefetch_moneyflow"


def _now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def prefetch_moneyflow(db: Session) -> dict[str, Any]:
    try:
        ts.require_token()
    except ts.TushareNotConfiguredError as exc:
        message = str(exc)
        save_job_run_meta(db, JOB_ID, last_message=message, last_success=False)
        return {"success": False, "skipped": True, "message": message}

    trade_date = latest_open_yyyymmdd(db)
    try:
        rows = fetch_moneyflow_rows(trade_date)
    except Exception as exc:  # noqa: BLE001
        message = f"moneyflow 失败: {exc}"
        save_job_run_meta(db, JOB_ID, last_message=message[:500], last_success=False)
        return {"success": False, "skipped": True, "message": message, "trade_date": trade_date}

    if not rows:
        message = f"无 moneyflow 数据（trade_date={trade_date}）"
        save_job_run_meta(db, JOB_ID, last_message=message, last_success=False)
        return {"success": False, "skipped": True, "message": message, "trade_date": trade_date}

    fetched_at = _now_iso()
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
            "dataset": "moneyflow",
            "trade_date": trade_date,
            "payload": json.dumps(rows, ensure_ascii=False),
            "fetched_at": fetched_at,
        },
    )
    db.commit()
    message = f"moneyflow 预拉 {len(rows)} 条（trade_date={trade_date}）"
    save_job_run_meta(db, JOB_ID, last_message=message, last_success=True)
    return {
        "success": True,
        "skipped": False,
        "message": message,
        "trade_date": trade_date,
        "written": 1,
    }

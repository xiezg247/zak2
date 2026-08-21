"""停牌日同步：Tushare suspend_d → app.symbol_suspend_days。"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.schemas.ops import SyncResult
from app.domains.market import tushare_client as ts
from app.domains.market.tushare_screener import latest_open_yyyymmdd, ts_code_to_tf
from app.services.ops.scheduler import save_job_run_meta

JOB_ID = "sync_suspend_daily"


def _yyyymmdd_to_iso(d: str) -> str:
    s = str(d or "").replace("-", "")[:8]
    if len(s) != 8:
        return str(d or "")
    return f"{s[:4]}-{s[4:6]}-{s[6:8]}"


def _tf_to_symbol_exchange(tf: str) -> tuple[str, str] | None:
    if "." not in tf:
        return None
    exch, sym = tf.split(".", 1)
    mapping = {"SHSE": "SSE", "SZSE": "SZSE", "BJSE": "BSE"}
    return sym, mapping.get(exch, exch)


def sync_suspend_daily(db: Session) -> SyncResult:
    try:
        ts.require_token()
    except ts.TushareNotConfiguredError as exc:
        message = str(exc)
        save_job_run_meta(db, JOB_ID, last_message=message, last_success=False)
        return SyncResult(success=False, skipped=True, message=message)

    trade_date = latest_open_yyyymmdd(db)
    try:
        rows = ts.query(
            "suspend_d",
            {"trade_date": trade_date, "suspend_type": "S"},
            fields="ts_code,trade_date,suspend_type",
        )
    except Exception as exc:
        message = f"suspend_d 失败: {exc}"
        save_job_run_meta(db, JOB_ID, last_message=message[:500], last_success=False)
        return SyncResult(success=False, skipped=True, message=message, extra={"trade_date": trade_date})

    cal_date = _yyyymmdd_to_iso(trade_date)
    payload: list[dict[str, str]] = []
    for item in rows:
        tf = ts_code_to_tf(str(item.get("ts_code") or ""))
        pair = _tf_to_symbol_exchange(tf)
        if not pair:
            continue
        sym, exch = pair
        payload.append(
            {
                "symbol": sym,
                "exchange": exch,
                "cal_date": _yyyymmdd_to_iso(str(item.get("trade_date") or trade_date)),
                "suspend_type": str(item.get("suspend_type") or "S")[:1] or "S",
            }
        )

    if not payload:
        message = f"无停牌数据（trade_date={trade_date}）"
        save_job_run_meta(db, JOB_ID, last_message=message, last_success=False)
        return SyncResult(success=False, skipped=True, message=message, extra={"trade_date": trade_date})

    db.execute(text("DELETE FROM app.symbol_suspend_days WHERE cal_date = :d"), {"d": cal_date})
    db.execute(
        text(
            """
            INSERT INTO app.symbol_suspend_days (symbol, exchange, cal_date, suspend_type)
            VALUES (:symbol, :exchange, :cal_date, :suspend_type)
            ON CONFLICT (symbol, exchange, cal_date) DO UPDATE
            SET suspend_type = EXCLUDED.suspend_type
            """
        ),
        payload,
    )
    db.commit()
    message = f"停牌同步 {len(payload)} 条（cal_date={cal_date}）"
    save_job_run_meta(db, JOB_ID, last_message=message, last_success=True)
    return SyncResult(success=True, message=message, extra={"written": len(payload), "trade_date": trade_date})

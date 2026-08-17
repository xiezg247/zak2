"""同步 A 股列表（Tushare stock_basic → app.universe）。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services import tushare_client as ts
from app.services.ops.scheduler import save_job_run_meta

JOB_ID = "sync_universe"
UNIVERSE_SYNCED_AT_KEY = "universe_synced_at"
INSERT_CHUNK = 500

_SUFFIX = {"SH": "SSE", "SZ": "SZSE", "BJ": "BSE"}


def parse_ts_code(ts_code: str) -> tuple[str, str] | None:
    text_v = (ts_code or "").strip().upper()
    if "." not in text_v:
        return None
    code, suf = text_v.rsplit(".", 1)
    exch = _SUFFIX.get(suf)
    if not code or not exch:
        return None
    return code, exch


def rows_from_stock_basic(raw: list[dict]) -> tuple[list[dict], int]:
    rows: list[dict] = []
    seen: set[tuple[str, str]] = set()
    skipped = 0
    for item in raw:
        parsed = parse_ts_code(str(item.get("ts_code") or ""))
        if not parsed:
            skipped += 1
            continue
        symbol, exchange = parsed
        key = (symbol, exchange)
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            {
                "symbol": symbol,
                "exchange": exchange,
                "name": str(item.get("name") or "").strip(),
            }
        )
    return rows, skipped


def _fail(db: Session, message: str, *, skipped: int = 0) -> dict[str, Any]:
    save_job_run_meta(db, JOB_ID, last_message=message, last_success=False)
    return {"success": False, "message": message, "count": 0, "skipped": skipped}


def sync_universe(db: Session) -> dict[str, Any]:
    try:
        ts.require_token()
    except ts.TushareNotConfiguredError as exc:
        return _fail(db, str(exc))

    try:
        raw = ts.query(
            "stock_basic",
            {"list_status": "L"},
            fields="ts_code,name",
        )
        rows, skipped = rows_from_stock_basic(raw)
        if not rows:
            db.rollback()
            return _fail(db, "无有效标的", skipped=skipped)

        db.execute(text("DELETE FROM app.universe"))
        for i in range(0, len(rows), INSERT_CHUNK):
            chunk = rows[i : i + INSERT_CHUNK]
            params: dict[str, Any] = {}
            placeholders: list[str] = []
            for j, row in enumerate(chunk):
                placeholders.append(f"(:s{j}, :e{j}, :n{j})")
                params[f"s{j}"] = row["symbol"]
                params[f"e{j}"] = row["exchange"]
                params[f"n{j}"] = row["name"]
            db.execute(
                text(
                    f"INSERT INTO app.universe (symbol, exchange, name) VALUES {', '.join(placeholders)}"
                ),
                params,
            )

        synced_at = datetime.now().isoformat(timespec="seconds")
        db.execute(
            text(
                """
                INSERT INTO app.meta (key, value) VALUES (:k, :v)
                ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
                """
            ),
            {"k": UNIVERSE_SYNCED_AT_KEY, "v": synced_at},
        )
        db.commit()

        count = len(rows)
        message = f"已同步 A 股列表 {count} 条"
        if skipped:
            message += f"（跳过 {skipped}）"
        save_job_run_meta(db, JOB_ID, last_message=message, last_success=True)
        return {"success": True, "message": message, "count": count, "skipped": skipped}
    except HTTPException as exc:
        db.rollback()
        detail = exc.detail
        message = detail if isinstance(detail, str) else str(detail)
        return _fail(db, message)
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        return _fail(db, f"同步 A 股列表失败：{exc}")

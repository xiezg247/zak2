"""同步行业映射（Tushare 申万 L2 / stock_basic → app.stock_industry）。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services import tushare_client as ts
from app.services.ops.scheduler import save_job_run_meta
from app.services.ops.sync_universe import parse_ts_code

JOB_ID = "sync_stock_industry"
SYNCED_AT_KEY = "stock_industry_synced_at"
INSERT_CHUNK = 500


def rows_from_sw_members(raw: list[dict]) -> tuple[list[dict], int]:
    rows: list[dict] = []
    seen: set[tuple[str, str]] = set()
    skipped = 0
    for item in raw:
        if str(item.get("out_date") or "").strip():
            skipped += 1
            continue
        parsed = parse_ts_code(str(item.get("ts_code") or ""))
        if not parsed:
            skipped += 1
            continue
        symbol, exchange = parsed
        l1 = str(item.get("l1_name") or "").strip()
        l2 = str(item.get("l2_name") or "").strip()
        industry = l2 or l1
        if not industry:
            skipped += 1
            continue
        key = (symbol, exchange)
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            {
                "symbol": symbol,
                "exchange": exchange,
                "industry": industry,
                "industry_l1": l1,
                "source": "sw2021_l2",
            }
        )
    return rows, skipped


def rows_from_stock_basic_industry(raw: list[dict]) -> tuple[list[dict], int]:
    rows: list[dict] = []
    seen: set[tuple[str, str]] = set()
    skipped = 0
    for item in raw:
        parsed = parse_ts_code(str(item.get("ts_code") or ""))
        if not parsed:
            skipped += 1
            continue
        symbol, exchange = parsed
        industry = str(item.get("industry") or "").strip()
        if not industry:
            skipped += 1
            continue
        key = (symbol, exchange)
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            {
                "symbol": symbol,
                "exchange": exchange,
                "industry": industry,
                "industry_l1": "",
                "source": "stock_basic",
            }
        )
    return rows, skipped


def _fail(db: Session, message: str, *, skipped: int = 0) -> dict[str, Any]:
    save_job_run_meta(db, JOB_ID, last_message=message, last_success=False)
    return {"success": False, "message": message, "count": 0, "skipped": skipped}


def sync_stock_industry(db: Session) -> dict[str, Any]:
    try:
        ts.require_token()
    except ts.TushareNotConfiguredError as exc:
        return _fail(db, str(exc))

    try:
        raw_sw = ts.query(
            "index_member_all",
            {"is_new": "Y"},
            fields="ts_code,l1_name,l2_name,out_date",
        )
        rows, skipped = rows_from_sw_members(raw_sw)
        source = "sw2021_l2"

        if not rows:
            raw_basic = ts.query(
                "stock_basic",
                {"list_status": "L"},
                fields="ts_code,industry",
            )
            rows, skipped = rows_from_stock_basic_industry(raw_basic)
            source = "stock_basic"

        if not rows:
            db.rollback()
            return _fail(db, "无有效行业映射", skipped=skipped)

        updated_at = datetime.now().isoformat(timespec="seconds")
        db.execute(text("DELETE FROM app.stock_industry"))
        for i in range(0, len(rows), INSERT_CHUNK):
            chunk = rows[i : i + INSERT_CHUNK]
            params: dict[str, Any] = {}
            placeholders: list[str] = []
            for j, row in enumerate(chunk):
                placeholders.append(f"(:s{j}, :e{j}, :ind{j}, :l1{j}, :src{j}, :upd{j})")
                params[f"s{j}"] = row["symbol"]
                params[f"e{j}"] = row["exchange"]
                params[f"ind{j}"] = row["industry"]
                params[f"l1{j}"] = row["industry_l1"]
                params[f"src{j}"] = row["source"]
                params[f"upd{j}"] = updated_at
            db.execute(
                text(
                    "INSERT INTO app.stock_industry "
                    "(symbol, exchange, industry, industry_l1, source, updated_at) "
                    f"VALUES {', '.join(placeholders)}"
                ),
                params,
            )

        synced_at = updated_at
        db.execute(
            text(
                """
                INSERT INTO app.meta (key, value) VALUES (:k, :v)
                ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
                """
            ),
            {"k": SYNCED_AT_KEY, "v": synced_at},
        )
        db.commit()

        count = len(rows)
        message = f"已同步行业映射 {count} 条（{source}）"
        if skipped:
            message += f"（跳过 {skipped}）"
        save_job_run_meta(db, JOB_ID, last_message=message, last_success=True)
        return {
            "success": True,
            "message": message,
            "count": count,
            "skipped": skipped,
            "source": source,
        }
    except HTTPException as exc:
        db.rollback()
        detail = exc.detail
        message = detail if isinstance(detail, str) else str(detail)
        return _fail(db, message)
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        return _fail(db, f"同步行业映射失败：{exc}")

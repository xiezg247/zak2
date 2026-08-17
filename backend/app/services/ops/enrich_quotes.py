"""行情因子 enrich：Tushare → Redis quote 补丁。"""

from __future__ import annotations

from typing import Any

import redis
from sqlalchemy.orm import Session

from app.core.settings import get_settings
from app.services import tushare_client as ts
from app.services.ops.scheduler import save_job_run_meta
from app.services.quote_factor_patch import apply_factor_patches
from app.services.quotes import get_quote_store
from app.services.tushare_screener import (
    fetch_daily_basic_rows,
    fetch_moneyflow_rows,
    latest_open_yyyymmdd,
    ts_code_to_tf,
)

JOB_ID = "enrich_market_quotes"


def _net_mf(item: dict[str, Any]) -> float:
    net = ts.safe_float(item.get("net_mf_amount"))
    if net == 0:
        buy = ts.safe_float(item.get("buy_lg_amount")) + ts.safe_float(item.get("buy_elg_amount"))
        sell = ts.safe_float(item.get("sell_lg_amount")) + ts.safe_float(item.get("sell_elg_amount"))
        net = buy - sell
    return net


def enrich_market_quotes(db: Session) -> dict[str, Any]:
    try:
        ts.require_token()
    except ts.TushareNotConfiguredError as exc:
        message = str(exc)
        save_job_run_meta(db, JOB_ID, last_message=message, last_success=False)
        return {"success": False, "skipped": True, "message": message}

    store = get_quote_store()
    if not store.meta().get("available"):
        message = "Redis 不可用或无行情，请先启动 quote-collector"
        save_job_run_meta(db, JOB_ID, last_message=message, last_success=False)
        return {"success": False, "skipped": True, "message": message}

    trade_date = latest_open_yyyymmdd(db)
    notes: list[str] = []
    patches: dict[str, dict[str, float]] = {}

    try:
        basic_rows = fetch_daily_basic_rows(trade_date)
    except Exception as exc:
        basic_rows = []
        notes.append(f"daily_basic 失败: {exc}")

    for item in basic_rows:
        tf = ts_code_to_tf(str(item.get("ts_code") or ""))
        if not tf or "." not in tf:
            continue
        patches.setdefault(tf, {})
        patches[tf].update(
            {
                "turnover_rate": ts.safe_float(item.get("turnover_rate")),
                "volume_ratio": ts.safe_float(item.get("volume_ratio")),
                "total_mv": ts.safe_float(item.get("total_mv")),
                "circ_mv": ts.safe_float(item.get("circ_mv")),
            }
        )

    try:
        flow_rows = fetch_moneyflow_rows(trade_date)
    except Exception as exc:
        flow_rows = []
        notes.append(f"moneyflow 失败: {exc}")

    for item in flow_rows:
        tf = ts_code_to_tf(str(item.get("ts_code") or ""))
        if not tf or "." not in tf:
            continue
        patches.setdefault(tf, {})
        patches[tf]["net_mf_amount"] = _net_mf(item)

    if not patches:
        message = "无 Tushare 因子数据（可能积分不足或非交易日）"
        if notes:
            message += "；" + "；".join(notes)
        save_job_run_meta(db, JOB_ID, last_message=message, last_success=False)
        return {"success": False, "skipped": True, "message": message, "trade_date": trade_date}

    client = redis.Redis.from_url(get_settings().redis_url, decode_responses=True)
    try:
        result = apply_factor_patches(client, patches)
    finally:
        client.close()
    updated = int(result.get("updated") or 0)
    if updated <= 0:
        message = "无已存在的行情键可补丁，请先跑 quote-collector"
        save_job_run_meta(db, JOB_ID, last_message=message, last_success=False)
        return {"success": False, "skipped": True, "message": message, "trade_date": trade_date}

    message = f"已更新 {updated} 只因子（trade_date={trade_date}）"
    if notes:
        message += "；" + "；".join(notes)
    save_job_run_meta(db, JOB_ID, last_message=message, last_success=True)
    return {
        "success": True,
        "skipped": False,
        "message": message,
        "trade_date": trade_date,
        "updated": updated,
        "seq": result.get("seq"),
    }

"""ARQ：回测异步任务。"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
from typing import Any

from fastapi import HTTPException

from app.core.db import SessionLocal
from app.core.settings import get_settings
from app.repositories import backtest as repo
from app.schemas.backtest import BacktestRunRequest, BatchBacktestRequest, OptimizeBacktestRequest
from app.services.backtest_bars import bars_to_records
from app.services.backtest_optimize import expand_ma_grid
from app.services.backtest_settings import build_strategy_setting


def _fail(exc: BaseException) -> dict[str, Any]:
    if isinstance(exc, HTTPException):
        return {"success": False, "error": str(exc.detail)}
    return {"success": False, "error": str(exc)}


def _use_subprocess() -> bool:
    settings = get_settings()
    if settings.backtest_subprocess:
        return True
    return os.environ.get("BACKTEST_SUBPROCESS", "").strip() in {"1", "true", "TRUE", "yes"}


def _run_via_subprocess(payload: dict[str, Any]) -> dict[str, Any]:
    settings = get_settings()
    proc = subprocess.run(
        [sys.executable, "-m", "app.worker.backtest_subprocess"],
        input=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        capture_output=True,
        timeout=settings.backtest_task_timeout_s,
        check=False,
    )
    if proc.returncode != 0:
        err = proc.stderr.decode("utf-8", errors="replace")[:500]
        try:
            body = json.loads(proc.stdout.decode("utf-8") or "{}")
            err = str(body.get("error") or err)
        except json.JSONDecodeError:
            pass
        raise RuntimeError(err or f"subprocess exit {proc.returncode}")
    body = json.loads(proc.stdout.decode("utf-8"))
    if not body.get("ok"):
        raise RuntimeError(str(body.get("error") or "subprocess failed"))
    return dict(body["result"])


def _run_single(user_id: str, payload: dict) -> dict[str, Any]:
    db = SessionLocal()
    try:
        req = BacktestRunRequest.model_validate(payload)
        out = repo.BacktestRepository(db, user_id).execute_single(req)
        if out.status == "failed":
            return {"success": False, "error": out.error_message or "failed", "result_ref": out.id}
        return {"success": True, "result_ref": out.id}
    except Exception as exc:  # noqa: BLE001
        return _fail(exc)
    finally:
        db.close()


def _execute_with_optional_subprocess(
    db,
    user_id: str,
    req: BacktestRunRequest,
    *,
    batch_id: str | None,
    source: str,
) -> Any:
    if not _use_subprocess() and source == "single":
        return repo.BacktestRepository(db, user_id).execute_single(req, batch_id=batch_id, source=source)

    # batch/optimize：加载 K 线后子进程跑引擎，父进程落库
    bars = repo.BacktestRepository(db, user_id).load_bars_for_request(req)
    setting = build_strategy_setting(req)
    params = {
        "fast_window": req.fast_window,
        "slow_window": req.slow_window,
        "capital": req.capital,
        "rate": req.rate,
        "slippage": req.slippage,
        "stamp_duty": req.stamp_duty,
        "adx_period": req.adx_period,
        "adx_threshold": req.adx_threshold,
        "trailing_stop_pct": req.trailing_stop_pct,
        "interval": req.interval or "d",
        "max_trading_days": req.max_trading_days,
        "setting": setting,
    }
    try:
        if _use_subprocess() or source in {"batch", "optimize"}:
            result = _run_via_subprocess(
                {
                    "bar_records": bars_to_records(bars),
                    "vt_symbol": req.vt_symbol,
                    "strategy_id": req.strategy,
                    "setting": setting,
                    "start": req.start_date,
                    "end": req.end_date,
                    "capital": req.capital,
                    "rate": req.rate,
                    "slippage": req.slippage,
                    "stamp_duty": req.stamp_duty,
                    "interval": req.interval or "d",
                }
            )
        else:
            result = repo.BacktestRepository(db, user_id).run_vnpy(req, bars)
        row = repo.BacktestRepository(db, user_id).save_run(
            vt_symbol=req.vt_symbol,
            strategy=req.strategy,
            interval=req.interval or "d",
            start_date=req.start_date,
            end_date=req.end_date,
            result=result,
            source=source,
            batch_id=batch_id,
            engine="vnpy",
            params=params,
            status="success",
        )
        return repo.BacktestRepository(db, user_id).to_out(row, detail=True)
    except Exception as exc:  # noqa: BLE001
        detail = str(exc.detail) if isinstance(exc, HTTPException) else str(exc)
        row = repo.BacktestRepository(db, user_id).save_run(
            vt_symbol=req.vt_symbol,
            strategy=req.strategy,
            interval=req.interval or "d",
            start_date=req.start_date,
            end_date=req.end_date,
            result={},
            source=source,
            batch_id=batch_id,
            engine="vnpy",
            params=params,
            status="failed",
            error_message=detail,
        )
        return repo.BacktestRepository(db, user_id).to_out(row, detail=True)


def _run_batch(user_id: str, payload: dict, batch_id: str) -> dict[str, Any]:
    db = SessionLocal()
    try:
        req = BatchBacktestRequest.model_validate(payload)
        last_id = None
        failed_count = 0
        for symbol in req.symbols:
            single = BacktestRunRequest(
                vt_symbol=symbol,
                strategy=req.strategy,
                interval=req.interval,
                start_date=req.start_date,
                end_date=req.end_date,
                fast_window=req.fast_window,
                slow_window=req.slow_window,
                capital=req.capital,
                rate=req.rate,
                slippage=req.slippage,
                stamp_duty=req.stamp_duty,
                adx_period=req.adx_period,
                adx_threshold=req.adx_threshold,
                trailing_stop_pct=req.trailing_stop_pct,
                max_trading_days=req.max_trading_days,
            )
            out = _execute_with_optional_subprocess(
                db, user_id, single, batch_id=batch_id, source="batch"
            )
            last_id = out.id
            if out.status == "failed":
                failed_count += 1
        return {
            "success": True,
            "result_ref": last_id or batch_id,
            "failed_count": failed_count,
        }
    except Exception as exc:  # noqa: BLE001
        return _fail(exc)
    finally:
        db.close()


def _run_optimize(user_id: str, payload: dict, batch_id: str) -> dict[str, Any]:
    db = SessionLocal()
    try:
        req = OptimizeBacktestRequest.model_validate(payload)
        combos = expand_ma_grid(req.space)
        last_id = None
        failed_count = 0
        for combo in combos:
            single = BacktestRunRequest(
                vt_symbol=req.vt_symbol,
                strategy=req.strategy,
                interval=req.interval,
                start_date=req.start_date,
                end_date=req.end_date,
                fast_window=combo["fast_window"],
                slow_window=combo["slow_window"],
                capital=req.capital,
                rate=req.rate,
                slippage=req.slippage,
                stamp_duty=req.stamp_duty,
                adx_period=req.adx_period,
                adx_threshold=req.adx_threshold,
                trailing_stop_pct=req.trailing_stop_pct,
                max_trading_days=req.max_trading_days,
            )
            out = _execute_with_optional_subprocess(
                db, user_id, single, batch_id=batch_id, source="optimize"
            )
            last_id = out.id
            if out.status == "failed":
                failed_count += 1
        return {
            "success": True,
            "result_ref": last_id or batch_id,
            "failed_count": failed_count,
            "combo_count": len(combos),
        }
    except Exception as exc:  # noqa: BLE001
        return _fail(exc)
    finally:
        db.close()


async def run_backtest_single(ctx: dict, *, user_id: str, payload: dict) -> dict:
    _ = ctx
    return await asyncio.to_thread(_run_single, user_id, payload)


async def run_backtest_batch(ctx: dict, *, user_id: str, payload: dict, batch_id: str) -> dict:
    _ = ctx
    return await asyncio.to_thread(_run_batch, user_id, payload, batch_id)


async def run_backtest_optimize(ctx: dict, *, user_id: str, payload: dict, batch_id: str) -> dict:
    _ = ctx
    return await asyncio.to_thread(_run_optimize, user_id, payload, batch_id)

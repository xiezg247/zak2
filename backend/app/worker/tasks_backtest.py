"""ARQ：回测异步任务。"""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import HTTPException

from app.core.db import SessionLocal
from app.schemas.backtest import BacktestRunRequest, BatchBacktestRequest
from app.services import backtest_repo as repo


def _fail(exc: BaseException) -> dict[str, Any]:
    if isinstance(exc, HTTPException):
        return {"success": False, "error": str(exc.detail)}
    return {"success": False, "error": str(exc)}


def _run_single(user_id: str, payload: dict) -> dict[str, Any]:
    db = SessionLocal()
    try:
        req = BacktestRunRequest.model_validate(payload)
        out = repo.execute_single(db, user_id, req)
        return {"success": True, "result_ref": out.id}
    except Exception as exc:  # noqa: BLE001
        return _fail(exc)
    finally:
        db.close()


def _run_batch(user_id: str, payload: dict, batch_id: str) -> dict[str, Any]:
    db = SessionLocal()
    try:
        req = BatchBacktestRequest.model_validate(payload)
        last_id = None
        last_error = None
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
            )
            try:
                out = repo.execute_single(db, user_id, single, batch_id=batch_id, source="batch")
                last_id = out.id
            except Exception as exc:  # noqa: BLE001
                last_error = f"{symbol}: {exc}"
        return {
            "success": True,
            "result_ref": last_id or batch_id,
            "error": last_error,
        }
    except Exception as exc:  # noqa: BLE001
        return _fail(exc)
    finally:
        db.close()


async def run_backtest_single(ctx: dict, *, user_id: str, payload: dict) -> dict:
    _ = ctx
    return await asyncio.to_thread(_run_single, user_id, payload)


async def run_backtest_batch(
    ctx: dict, *, user_id: str, payload: dict, batch_id: str
) -> dict:
    _ = ctx
    return await asyncio.to_thread(_run_batch, user_id, payload, batch_id)

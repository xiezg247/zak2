"""ARQ：选股异步任务。"""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import HTTPException

from app.core.db import SessionLocal
from app.repositories import screener as repo
from app.schemas.screener import (
    ConditionRunRequest,
    PatternRunRequest,
    RecipeRunRequest,
    ReferencePeerRequest,
)
from app.services.engine import run_condition_screen, run_recipe_screen
from app.services.pattern_screen import run_pattern_screen
from app.services.reference_peer import run_reference_peer


def _fail(exc: BaseException) -> dict[str, Any]:
    if isinstance(exc, HTTPException):
        return {"success": False, "error": str(exc.detail)}
    return {"success": False, "error": str(exc)}


def _run_condition(user_id: str, payload: dict) -> dict[str, Any]:
    db = SessionLocal()
    try:
        req = ConditionRunRequest.model_validate(payload)
        prev = repo.ScreenerRunRepository(db, user_id).latest_run_symbols()
        result = run_condition_screen(req, previous_symbols=prev, db=db)
        run = repo.ScreenerRunRepository(db, user_id).save_run(
            condition=result["condition"],
            source=result["source"],
            result=result,
        )
        return {"success": True, "result_ref": run.id}
    except Exception as exc:  # noqa: BLE001
        return _fail(exc)
    finally:
        db.close()


def _run_recipe(user_id: str, payload: dict) -> dict[str, Any]:
    db = SessionLocal()
    try:
        req = RecipeRunRequest.model_validate(payload)
        prev = repo.ScreenerRunRepository(db, user_id).latest_run_symbols()
        result = run_recipe_screen(req, previous_symbols=prev, db=db, user_id=user_id)
        run = repo.ScreenerRunRepository(db, user_id).save_run(
            condition=result["condition"],
            source=result["source"],
            result=result,
        )
        return {"success": True, "result_ref": run.id}
    except Exception as exc:  # noqa: BLE001
        return _fail(exc)
    finally:
        db.close()


def _run_pattern(user_id: str, payload: dict) -> dict[str, Any]:
    db = SessionLocal()
    try:
        req = PatternRunRequest.model_validate(payload)
        prev = repo.ScreenerRunRepository(db, user_id).latest_run_symbols()
        result = run_pattern_screen(req, db=db, previous_symbols=prev)
        run = repo.ScreenerRunRepository(db, user_id).save_run(
            condition=result["condition"],
            source=result["source"],
            result=result,
        )
        return {"success": True, "result_ref": run.id}
    except Exception as exc:  # noqa: BLE001
        return _fail(exc)
    finally:
        db.close()


def _run_reference_peer(user_id: str, payload: dict) -> dict[str, Any]:
    db = SessionLocal()
    try:
        req = ReferencePeerRequest.model_validate(payload)
        prev = repo.ScreenerRunRepository(db, user_id).latest_run_symbols()
        result = run_reference_peer(req, db=db, previous_symbols=prev)
        run = repo.ScreenerRunRepository(db, user_id).save_run(
            condition=result["condition"],
            source=result["source"],
            result=result,
        )
        return {"success": True, "result_ref": run.id}
    except Exception as exc:  # noqa: BLE001
        return _fail(exc)
    finally:
        db.close()


async def run_screener_condition(ctx: dict, *, user_id: str, payload: dict) -> dict:
    _ = ctx
    return await asyncio.to_thread(_run_condition, user_id, payload)


async def run_screener_recipe(ctx: dict, *, user_id: str, payload: dict) -> dict:
    _ = ctx
    return await asyncio.to_thread(_run_recipe, user_id, payload)


async def run_screener_pattern(ctx: dict, *, user_id: str, payload: dict) -> dict:
    _ = ctx
    return await asyncio.to_thread(_run_pattern, user_id, payload)


async def run_screener_reference_peer(ctx: dict, *, user_id: str, payload: dict) -> dict:
    _ = ctx
    return await asyncio.to_thread(_run_reference_peer, user_id, payload)

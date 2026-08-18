"""ARQ worker：执行 Ops RUNNERS（含 bars 互斥）。"""

from __future__ import annotations

import asyncio
from typing import Any

from pydantic import BaseModel

from app.core.db import SessionLocal
from app.services.ops import sync_bilibili_feed as ops_sync_bilibili_feed
from app.services.ops.bars_lock import BARS_JOBS, release_bars, try_acquire_bars
from app.services.ops.catalog import RUNNABLE_JOB_IDS
from app.services.ops.runners import RUNNERS, needs_user_id


def _execute_sync(
    ops_job_id: str,
    *,
    user_id: str | None,
    force: bool,
) -> dict[str, Any]:
    if ops_job_id not in RUNNABLE_JOB_IDS or ops_job_id not in RUNNERS:
        raise ValueError(f"未知或不可执行任务: {ops_job_id}")

    bars_token: str | None = None
    if ops_job_id in BARS_JOBS:
        bars_token = try_acquire_bars()
        if bars_token is None:
            return {
                "success": False,
                "skipped": False,
                "message": "bars 任务互斥：已有同类任务在执行",
            }

    db = SessionLocal()
    try:
        if ops_job_id == ops_sync_bilibili_feed.JOB_ID:
            result = ops_sync_bilibili_feed.sync_bilibili_feed(db, force=force)
        else:
            runner = RUNNERS[ops_job_id]
            if needs_user_id(ops_job_id):
                if not (user_id or "").strip():
                    raise ValueError(f"{ops_job_id} 需要 user_id")
                result = runner(db, user_id=user_id)
            else:
                result = runner(db)
        if isinstance(result, BaseModel):
            return result.model_dump()
        return result
    finally:
        db.close()
        if bars_token is not None:
            release_bars(bars_token)


async def run_ops_job(
    ctx: dict,
    ops_job_id: str,
    *,
    user_id: str | None = None,
    force: bool = False,
) -> dict:
    _ = ctx
    return await asyncio.to_thread(_execute_sync, ops_job_id, user_id=user_id, force=force)

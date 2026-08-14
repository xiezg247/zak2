"""ARQ worker：执行 Ops RUNNERS。"""

from __future__ import annotations

import asyncio
from typing import Any

from app.core.db import SessionLocal
from app.services import ops_sync_bilibili_feed
from app.services.ops_catalog import RUNNABLE_JOB_IDS
from app.services.ops_runners import RUNNERS, needs_user_id


def _execute_sync(
    ops_job_id: str,
    *,
    user_id: str | None,
    force: bool,
) -> dict[str, Any]:
    if ops_job_id not in RUNNABLE_JOB_IDS or ops_job_id not in RUNNERS:
        raise ValueError(f"未知或不可执行任务: {ops_job_id}")
    db = SessionLocal()
    try:
        if ops_job_id == ops_sync_bilibili_feed.JOB_ID:
            return ops_sync_bilibili_feed.sync_bilibili_feed(db, force=force)
        runner = RUNNERS[ops_job_id]
        if needs_user_id(ops_job_id):
            if not (user_id or "").strip():
                raise ValueError(f"{ops_job_id} 需要 user_id")
            return runner(db, user_id=user_id)
        return runner(db)
    finally:
        db.close()


async def run_ops_job(
    ctx: dict,
    ops_job_id: str,
    *,
    user_id: str | None = None,
    force: bool = False,
) -> dict:
    _ = ctx
    return await asyncio.to_thread(_execute_sync, ops_job_id, user_id=user_id, force=force)

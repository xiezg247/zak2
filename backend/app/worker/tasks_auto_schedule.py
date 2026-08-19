"""ARQ：自动任务执行。"""

from __future__ import annotations

import asyncio
from typing import Any

from app.core.db import SessionLocal
from app.services.ops import auto_schedule as ops_auto_schedule


def _run(task_id: int) -> dict[str, Any]:
    db = SessionLocal()
    try:
        out = ops_auto_schedule.run_task(db, task_id)
        return {
            "success": out.success,
            "skipped": out.skipped,
            "message": out.message,
            "extra": out.extra,
        }
    except Exception as exc:
        return {"success": False, "message": str(exc)}
    finally:
        db.close()


async def run_auto_schedule_task(ctx: dict, *, task_id: str) -> dict:
    _ = ctx
    return await asyncio.to_thread(_run, int(task_id))

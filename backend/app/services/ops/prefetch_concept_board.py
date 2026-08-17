"""概念板块预拉：复用 sync_sector_flow_daily（含 ths/dc 概念资金）。"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.schemas.ops import SyncResult
from app.services.ops.scheduler import save_job_run_meta
from app.services.ops.sync_sector import sync_sector_flow_daily

JOB_ID = "prefetch_concept_board"


def prefetch_concept_board(db: Session) -> SyncResult:
    child = sync_sector_flow_daily(db)
    skipped = bool(child.skipped)
    success = bool(child.success)
    child_msg = str(child.message or "")
    if success and not skipped:
        message = f"概念预拉（复用 sector sync）：{child_msg}"
        last_success = True
    else:
        message = child_msg or "概念预拉失败"
        last_success = False
    save_job_run_meta(db, JOB_ID, last_message=message, last_success=last_success)
    extra: dict[str, Any] = {}
    days = child.extra.get("days")
    if days is not None:
        extra["days"] = days
    return SyncResult(success=success, skipped=skipped, message=message, extra=extra)

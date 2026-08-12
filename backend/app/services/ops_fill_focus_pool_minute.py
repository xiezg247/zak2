"""关注池 1m K 补全占位：zak2 尚未接入分钟线补全管线。"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.services.ops_scheduler import save_job_run_meta

JOB_ID = "fill_focus_pool_minute"
_MESSAGE = "zak2 尚未接入关注池 1m K 补全管线"


def fill_focus_pool_minute(db: Session) -> dict[str, Any]:
    save_job_run_meta(db, JOB_ID, last_message=_MESSAGE, last_success=False)
    return {"success": False, "skipped": True, "message": _MESSAGE}

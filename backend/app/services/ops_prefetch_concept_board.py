"""概念板块预拉：复用 sync_sector_flow_daily（含 ths/dc 概念资金）。"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.services.ops_scheduler import save_job_run_meta
from app.services.ops_sync_sector import sync_sector_flow_daily

JOB_ID = "prefetch_concept_board"


def prefetch_concept_board(db: Session) -> dict[str, Any]:
    child = sync_sector_flow_daily(db)
    skipped = bool(child.get("skipped"))
    success = bool(child.get("success"))
    child_msg = str(child.get("message") or "")
    if success and not skipped:
        message = f"概念预拉（复用 sector sync）：{child_msg}"
        last_success = True
    else:
        message = child_msg or "概念预拉失败"
        last_success = False
    save_job_run_meta(db, JOB_ID, last_message=message, last_success=last_success)
    out: dict[str, Any] = {
        "success": success,
        "skipped": skipped,
        "message": message,
    }
    if "days" in child:
        out["days"] = child["days"]
    return out

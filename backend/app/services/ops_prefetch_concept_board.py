"""同花顺概念预拉占位：zak2 尚未接入概念预热落点。"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.services.ops_scheduler import save_job_run_meta

JOB_ID = "prefetch_concept_board"
_MESSAGE = "zak2 尚未接入同花顺概念预热落点，无法预拉 concept board"


def prefetch_concept_board(db: Session) -> dict[str, Any]:
    save_job_run_meta(db, JOB_ID, last_message=_MESSAGE, last_success=False)
    return {"success": False, "skipped": True, "message": _MESSAGE}

"""雷达展望扫描占位：zak2 尚未接入 horizon/predict 管线。"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.services.ops_scheduler import save_job_run_meta

JOB_ID = "scan_horizon_outlook"
_MESSAGE = "zak2 尚未接入雷达展望扫描管线，无法写入 radar_horizon/predict cache"


def scan_horizon_outlook(db: Session) -> dict[str, Any]:
    save_job_run_meta(db, JOB_ID, last_message=_MESSAGE, last_success=False)
    return {"success": False, "skipped": True, "message": _MESSAGE}

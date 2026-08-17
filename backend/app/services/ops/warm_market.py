"""市场摘要预热（情绪周期短 TTL 缓存）。"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.services.emotion_cycle import build_emotion_cycle
from app.services.ops.scheduler import save_job_run_meta

JOB_ID = "warm_market_summary"


def warm_market_summary(db: Session) -> dict[str, Any]:
    snap = build_emotion_cycle(db, force=True)
    message = f"已预热情绪周期：{snap['stage_label']}"
    save_job_run_meta(db, JOB_ID, last_message=message, last_success=True)
    return {
        "success": True,
        "message": message,
        "stage": snap["stage"],
        "stage_label": snap["stage_label"],
        "source": snap.get("source"),
    }

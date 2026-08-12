"""自选策略信号预热占位：zak2 尚未接入策略引擎。"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.services.ops_scheduler import save_job_run_meta

JOB_ID = "warm_watchlist_strategy_cache"
_MESSAGE = "zak2 尚未接入策略引擎，无法预热 watchlist_signal/position cache"


def warm_watchlist_strategy_cache(db: Session) -> dict[str, Any]:
    save_job_run_meta(db, JOB_ID, last_message=_MESSAGE, last_success=False)
    return {"success": False, "skipped": True, "message": _MESSAGE}

"""清理 cache schema 过期行（对齐 zak purge_stale_cache）。"""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.schemas.ops import PurgeResult
from app.services.ops.scheduler import save_job_run_meta

JOB_ID = "purge_stale_cache"


def _env_int(key: str, default: int) -> int:
    raw = os.getenv(key, str(default)).strip()
    try:
        return max(1, int(raw))
    except ValueError:
        return default


def _delete_count(db: Session, sql: str, params: dict[str, str]) -> int:
    result = db.execute(text(sql), params)
    return int(getattr(result, "rowcount", 0) or 0)


def purge_stale_cache(db: Session) -> PurgeResult:
    now = datetime.now(UTC)
    now_text = now.isoformat(timespec="seconds")
    signal_cutoff = (now - timedelta(days=_env_int("CACHE_SIGNAL_RETENTION_DAYS", 7))).isoformat(timespec="seconds")
    radar_snapshot_cutoff = (now - timedelta(days=_env_int("CACHE_RADAR_SNAPSHOT_RETENTION_DAYS", 30))).isoformat(
        timespec="seconds"
    )

    deleted: dict[str, int] = {
        "radar_ai_hint": _delete_count(
            db, "DELETE FROM cache.radar_ai_hint_cache WHERE expires_at < :c", {"c": now_text}
        ),
        "sector_flow_outlook_llm": _delete_count(
            db, "DELETE FROM cache.sector_flow_outlook_llm_cache WHERE expires_at < :c", {"c": now_text}
        ),
        "watchlist_signal": _delete_count(
            db, "DELETE FROM cache.watchlist_signal_cache WHERE updated_at < :c", {"c": signal_cutoff}
        ),
        "watchlist_position": _delete_count(
            db, "DELETE FROM cache.watchlist_position_cache WHERE updated_at < :c", {"c": signal_cutoff}
        ),
        "radar_predict": _delete_count(
            db, "DELETE FROM cache.radar_predict_cache WHERE computed_at < :c", {"c": radar_snapshot_cutoff}
        ),
        "radar_horizon": _delete_count(
            db, "DELETE FROM cache.radar_horizon_cache WHERE computed_at < :c", {"c": radar_snapshot_cutoff}
        ),
    }
    db.commit()

    total = sum(deleted.values())
    parts = ", ".join(f"{name} {count}" for name, count in deleted.items() if count)
    message = f"清理 cache {total} 行（{parts or '无过期行'}）"
    save_job_run_meta(db, JOB_ID, last_message=message, last_success=True)
    return PurgeResult(deleted=deleted, total=total, message=message)

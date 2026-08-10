"""调度配置与 job 上次运行（app.meta / system.scheduler_config）。"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.ops_catalog import JOB_SPECS, JOBS_BY_ID, RUNNABLE_JOB_IDS
from app.services.scheduler_defaults import resolve_cron

_CONFIG_ID = "default"
_META_PREFIX = "scheduler/job_last_run/"
_MAX_MESSAGE_LEN = 500


def load_scheduler_config(db: Session) -> dict[str, Any]:
    row = db.execute(
        text("SELECT config_json, updated_at FROM system.scheduler_config WHERE id = :id"),
        {"id": _CONFIG_ID},
    ).mappings().first()
    if not row:
        return {"id": _CONFIG_ID, "config": {}, "updated_at": None}
    raw = row["config_json"]
    if isinstance(raw, str):
        raw = json.loads(raw) if raw.strip() else {}
    updated = row["updated_at"]
    return {
        "id": _CONFIG_ID,
        "config": raw or {},
        "updated_at": updated.isoformat() if hasattr(updated, "isoformat") else (str(updated) if updated else None),
    }


def save_scheduler_config(db: Session, config: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(config, dict):
        raise ValueError("config 必须是对象")
    db.execute(
        text(
            """
            INSERT INTO system.scheduler_config (id, config_json, updated_at)
            VALUES (:id, CAST(:cfg AS jsonb), NOW())
            ON CONFLICT (id) DO UPDATE
            SET config_json = EXCLUDED.config_json, updated_at = NOW()
            """
        ),
        {"id": _CONFIG_ID, "cfg": json.dumps(config, ensure_ascii=False)},
    )
    db.commit()
    return load_scheduler_config(db)


def patch_job_enabled(db: Session, job_id: str, enabled: bool) -> dict[str, Any]:
    if job_id not in JOBS_BY_ID:
        raise KeyError(job_id)
    loaded = load_scheduler_config(db)
    config = dict(loaded["config"] or {})
    attr = JOBS_BY_ID[job_id].config_attr
    job_cfg = dict(config.get(attr) or {})
    job_cfg["enabled"] = enabled
    config[attr] = job_cfg
    return save_scheduler_config(db, config)


def _meta_key(job_id: str) -> str:
    return f"{_META_PREFIX}{job_id}"


def load_job_run_meta(db: Session, job_id: str) -> dict[str, Any] | None:
    raw = db.execute(
        text("SELECT value FROM app.meta WHERE key = :k"),
        {"k": _meta_key(job_id)},
    ).scalar()
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except (TypeError, ValueError, json.JSONDecodeError):
        return None
    last_run_at = str(data.get("last_run_at") or "").strip()
    if not last_run_at:
        return None
    success_raw = data.get("last_success")
    return {
        "last_run_at": last_run_at,
        "last_message": str(data.get("last_message") or "").strip(),
        "last_success": None if success_raw is None else bool(success_raw),
    }


def save_job_run_meta(
    db: Session,
    job_id: str,
    *,
    last_message: str,
    last_success: bool | None,
) -> None:
    message = str(last_message or "").strip()
    if len(message) > _MAX_MESSAGE_LEN:
        message = message[: _MAX_MESSAGE_LEN - 1] + "…"
    payload = json.dumps(
        {
            "last_run_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
            "last_message": message,
            "last_success": last_success,
        },
        ensure_ascii=False,
    )
    db.execute(
        text(
            """
            INSERT INTO app.meta (key, value)
            VALUES (:k, :v)
            ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
            """
        ),
        {"k": _meta_key(job_id), "v": payload},
    )
    db.commit()


def list_scheduler_jobs(db: Session) -> list[dict[str, Any]]:
    loaded = load_scheduler_config(db)
    config = loaded["config"] or {}
    out: list[dict[str, Any]] = []
    for spec in JOB_SPECS:
        job_cfg = config.get(spec.config_attr) or {}
        if not isinstance(job_cfg, dict):
            job_cfg = {}
        meta = load_job_run_meta(db, spec.job_id)
        row: dict[str, Any] = {
            "job_id": spec.job_id,
            "name": spec.name,
            "description": spec.description,
            "runnable": spec.job_id in RUNNABLE_JOB_IDS,
            "run_hint": None if spec.job_id in RUNNABLE_JOB_IDS else "请用 zak CLI：job run " + spec.job_id,
            "enabled": bool(job_cfg.get("enabled", False)),
            "cron_hour": job_cfg.get("cron_hour"),
            "cron_minute": job_cfg.get("cron_minute"),
            "cron_day_of_week": job_cfg.get("cron_day_of_week"),
            "interval_seconds": job_cfg.get("interval_seconds"),
            "last_run": meta,
        }
        if spec.job_id in RUNNABLE_JOB_IDS:
            resolved = resolve_cron(spec.job_id, job_cfg)
            row["cron_hour"] = job_cfg.get("cron_hour", resolved["hour"])
            row["cron_minute"] = job_cfg.get("cron_minute", resolved["minute"])
            row["cron_day_of_week"] = job_cfg.get("cron_day_of_week", resolved["day_of_week"])
            if resolved.get("hours"):
                row["cron_hours"] = job_cfg.get("cron_hours") or ",".join(
                    map(str, resolved["hours"])
                )
        out.append(row)
    return out

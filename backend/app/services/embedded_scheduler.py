"""内嵌 APScheduler：调度全部 RUNNABLE_JOB_IDS。"""

from __future__ import annotations

import logging
import threading
from typing import Any

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.core.db import SessionLocal
from app.core.settings import get_settings
from app.services import scheduler_lock
from app.services import ops_sync_bilibili_feed
from app.services.ops_catalog import RUNNABLE_JOB_IDS
from app.services.ops_runners import RUNNERS, needs_user_id
from app.services.ops_scheduler import load_scheduler_config
from app.services.scheduler_defaults import resolve_cron

_logger = logging.getLogger(__name__)

_scheduler: BackgroundScheduler | None = None
_locks: dict[str, threading.Lock] = {job_id: threading.Lock() for job_id in RUNNABLE_JOB_IDS}
_running: set[str] = set()
_running_guard = threading.Lock()
_BARS_JOBS = frozenset({"fill_watchlist_bars", "batch_fill_stale", "batch_download_universe"})


def _job_enabled(config: dict[str, Any], job_id: str) -> bool:
    cfg = config.get(job_id)
    if not isinstance(cfg, dict):
        return False
    return bool(cfg.get("enabled"))


def _run_job(job_id: str) -> None:
    settings = get_settings()
    if not settings.scheduler_effective_enabled:
        return

    lock = _locks[job_id]
    if not lock.acquire(blocking=False):
        _logger.info("embedded scheduler skip %s: already locked", job_id)
        return

    with _running_guard:
        if job_id in _BARS_JOBS and (_running & _BARS_JOBS):
            lock.release()
            _logger.info("embedded scheduler skip %s: another bars job running", job_id)
            return
        _running.add(job_id)

    token = scheduler_lock.make_token()
    if not scheduler_lock.try_acquire(job_id, token=token):
        _logger.info("embedded scheduler skip %s: distributed lock not acquired", job_id)
        with _running_guard:
            _running.discard(job_id)
        lock.release()
        return

    db = None
    try:
        db = SessionLocal()
        loaded = load_scheduler_config(db)
        config = dict(loaded.get("config") or {})
        if not _job_enabled(config, job_id):
            return

        if needs_user_id(job_id):
            user_id = (settings.scheduler_screen_user_id or "").strip()
            if not user_id:
                _logger.warning(
                    "embedded scheduler skip %s: SCHEDULER_SCREEN_USER_ID not set",
                    job_id,
                )
                return
            runner = RUNNERS[job_id]
            result = runner(db, user_id=user_id)
        elif job_id == ops_sync_bilibili_feed.JOB_ID:
            # 定时遵守 08–20 窗口；Ops 手动走 RUNNERS（force=True）
            result = ops_sync_bilibili_feed.sync_bilibili_feed(db, force=False)
        else:
            runner = RUNNERS[job_id]
            result = runner(db)

        _logger.info("embedded scheduler %s: %s", job_id, result.get("message"))
    except Exception:  # noqa: BLE001
        _logger.exception("embedded scheduler %s failed", job_id)
    finally:
        scheduler_lock.release(job_id, token)
        if db is not None:
            db.close()
        with _running_guard:
            _running.discard(job_id)
        lock.release()


def start_embedded_scheduler() -> None:
    global _scheduler
    settings = get_settings()
    if not settings.scheduler_effective_enabled:
        _logger.info("embedded scheduler disabled (scheduler_effective_enabled=False)")
        return
    if _scheduler is not None:
        return

    db = SessionLocal()
    try:
        config = dict(load_scheduler_config(db).get("config") or {})
    finally:
        db.close()

    sched = BackgroundScheduler(timezone="Asia/Shanghai")
    for job_id in sorted(RUNNABLE_JOB_IDS):
        job_cfg = config.get(job_id) if isinstance(config.get(job_id), dict) else {}
        cron = resolve_cron(job_id, job_cfg or {})
        day_of_week = cron["day_of_week"]
        minute = cron["minute"]
        hours = cron.get("hours")
        if hours is not None:
            trigger = CronTrigger(
                day_of_week=day_of_week,
                hour=",".join(map(str, hours)),
                minute=minute,
            )
        else:
            trigger = CronTrigger(
                day_of_week=day_of_week,
                hour=cron["hour"],
                minute=minute,
            )
        sched.add_job(
            _run_job,
            trigger,
            id=job_id,
            args=[job_id],
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )
    sched.start()
    _scheduler = sched
    _logger.info("embedded scheduler started (%d jobs)", len(RUNNABLE_JOB_IDS))


def stop_embedded_scheduler() -> None:
    global _scheduler
    if _scheduler is None:
        return
    _scheduler.shutdown(wait=False)
    _scheduler = None

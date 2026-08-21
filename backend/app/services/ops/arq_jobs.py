"""ARQ 入队、统一旁路索引与 JobOut 映射（Ops / screener / backtest）。"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any, cast

import redis
from arq import create_pool
from arq.connections import ArqRedis, RedisSettings
from arq.constants import job_key_prefix, result_key_prefix
from arq.jobs import Job, JobStatus

from app.core.redis_keys import (
    ARQ_JOBS_META_KEY_FMT,
    ARQ_JOBS_RECENT_MAX,
    ARQ_JOBS_RECENT_ZSET,
)
from app.core.settings import get_settings
from app.domains.screener.schemas import JobOut

logger = logging.getLogger(__name__)

_pool: ArqRedis | None = None

_IN_FLIGHT = {JobStatus.queued, JobStatus.deferred, JobStatus.in_progress}

SCREENER_FUNCS = {
    "screener.condition": "run_screener_condition",
    "screener.recipe": "run_screener_recipe",
    "screener.pattern": "run_screener_pattern",
    "screener.reference_peer": "run_screener_reference_peer",
}
BACKTEST_FUNCS = {
    "backtest.single": "run_backtest_single",
    "backtest.batch": "run_backtest_batch",
    "backtest.optimize": "run_backtest_optimize",
}


def ops_arq_id(ops_job_id: str) -> str:
    return f"ops:{ops_job_id}"


def _sync_redis() -> redis.Redis:
    return redis.Redis.from_url(get_settings().redis_url, decode_responses=True)


async def _arq_pool() -> ArqRedis:
    global _pool
    if _pool is None:
        settings = get_settings()
        _pool = await create_pool(
            RedisSettings.from_dsn(settings.redis_url),
            default_queue_name=settings.arq_queue_name,
        )
    return _pool


def index_job(
    client: redis.Redis,
    *,
    arq_id: str,
    kind: str,
    user_id: str | None,
    created_at: str,
    score_ms: int,
    **extra: str,
) -> None:
    mapping = {
        "kind": kind,
        "created_at": created_at,
        "user_id": user_id or "",
        **{k: str(v) for k, v in extra.items() if v is not None},
    }
    jobs_meta = ARQ_JOBS_META_KEY_FMT.format(job_id=arq_id)
    client.zadd(ARQ_JOBS_RECENT_ZSET, {arq_id: score_ms})
    client.hset(jobs_meta, mapping=mapping)
    client.zremrangebyrank(ARQ_JOBS_RECENT_ZSET, 0, -(ARQ_JOBS_RECENT_MAX + 1))


# 兼容旧名
def _index_ops_job(
    client: redis.Redis,
    *,
    arq_id: str,
    ops_job_id: str,
    user_id: str | None,
    created_at: str,
    score_ms: int,
) -> None:
    index_job(
        client,
        arq_id=arq_id,
        kind=f"ops.{ops_job_id}",
        user_id=user_id,
        created_at=created_at,
        score_ms=score_ms,
        ops_job_id=ops_job_id,
    )


async def _clear_arq_job_keys(pool: ArqRedis, job_id: str) -> None:
    queue = get_settings().arq_queue_name
    await pool.delete(job_key_prefix + job_id)
    await pool.delete(result_key_prefix + job_id)
    try:
        await pool.zrem(queue, job_id)
    except Exception:
        logger.warning("清理 ARQ job 键失败: %s", job_id)


async def enqueue_ops_job(
    ops_job_id: str,
    *,
    user_id: str | None = None,
    force: bool = False,
) -> str:
    stable_id = ops_arq_id(ops_job_id)
    pool = await _arq_pool()
    settings = get_settings()
    job_probe = Job(stable_id, redis=pool, _queue_name=settings.arq_queue_name)
    st = await job_probe.status()
    if st in _IN_FLIGHT:
        client = _sync_redis()
        meta = client.hgetall(ARQ_JOBS_META_KEY_FMT.format(job_id=stable_id)) or {}
        if not meta:
            now = datetime.now(UTC)
            index_job(
                client,
                arq_id=stable_id,
                kind=f"ops.{ops_job_id}",
                user_id=user_id,
                created_at=now.isoformat(),
                score_ms=int(now.timestamp() * 1000),
                ops_job_id=ops_job_id,
            )
        return stable_id

    if st in {JobStatus.complete, JobStatus.not_found}:
        await _clear_arq_job_keys(pool, stable_id)

    job = await pool.enqueue_job(
        "run_ops_job",
        ops_job_id,
        user_id=user_id,
        force=force,
        _job_id=stable_id,
        _queue_name=settings.arq_queue_name,
    )
    if job is None:
        st2 = await Job(stable_id, redis=pool, _queue_name=settings.arq_queue_name).status()
        if st2 in _IN_FLIGHT:
            return stable_id
        raise RuntimeError(f"enqueue 失败：{ops_job_id}")

    now = datetime.now(UTC)
    index_job(
        _sync_redis(),
        arq_id=job.job_id,
        kind=f"ops.{ops_job_id}",
        user_id=user_id,
        created_at=now.isoformat(),
        score_ms=int(now.timestamp() * 1000),
        ops_job_id=ops_job_id,
    )
    return job.job_id


def enqueue_ops_job_sync(
    ops_job_id: str,
    *,
    user_id: str | None = None,
    force: bool = False,
) -> str:
    return asyncio.run(enqueue_ops_job(ops_job_id, user_id=user_id, force=force))


async def enqueue_app_job(
    *,
    function: str,
    kind: str,
    user_id: str,
    payload: dict[str, Any],
    batch_id: str | None = None,
) -> str:
    pool = await _arq_pool()
    settings = get_settings()
    queue = settings.arq_backtest_queue_name if kind.startswith("backtest.") else settings.arq_queue_name
    kwargs: dict[str, Any] = {"user_id": user_id, "payload": payload}
    if batch_id is not None:
        kwargs["batch_id"] = batch_id
    job = await pool.enqueue_job(function, _queue_name=queue, **kwargs)
    if job is None:
        raise RuntimeError(f"enqueue 失败：{kind}")
    now = datetime.now(UTC)
    extra: dict[str, str] = {"queue": queue}
    if batch_id:
        extra["batch_id"] = batch_id
    index_job(
        _sync_redis(),
        arq_id=job.job_id,
        kind=kind,
        user_id=user_id,
        created_at=now.isoformat(),
        score_ms=int(now.timestamp() * 1000),
        **extra,
    )
    return job.job_id


def _job_out_from_arq(
    *,
    job_id: str,
    kind: str,
    status_name: str,
    result_info: Any | None,
    created_at_fallback: str,
) -> JobOut:
    created_at = created_at_fallback
    updated_at = created_at_fallback
    status = "pending"
    progress = 0.0
    error: str | None = None
    result_ref: str | None = None
    ops_job_id = kind.removeprefix("ops.") if kind.startswith("ops.") else ""

    if status_name in {"queued", "deferred"}:
        status, progress = "pending", 0.0
    elif status_name == "in_progress":
        status, progress = "running", 0.5
    elif status_name == "complete":
        progress = 1.0
        if result_info is None:
            status = "failed"
            error = "无结果"
        elif not getattr(result_info, "success", False):
            status = "failed"
            error = str(getattr(result_info, "result", "failed"))
        else:
            raw = getattr(result_info, "result", None)
            if isinstance(raw, dict):
                if kind.startswith("ops."):
                    ok = True if ops_job_id == "purge_stale_cache" else bool(raw.get("success", True))
                    msg = str(raw.get("message") or "完成")
                    if raw.get("skipped") or ok:
                        status, result_ref = "success", msg
                    else:
                        status, error = "failed", msg
                else:
                    if bool(raw.get("success", True)):
                        status = "success"
                        result_ref = str(raw.get("result_ref") or raw.get("message") or "")
                    else:
                        status = "failed"
                        error = str(raw.get("error") or raw.get("message") or "failed")
            else:
                status, result_ref = "success", str(raw)
        if result_info is not None:
            if getattr(result_info, "enqueue_time", None):
                created_at = result_info.enqueue_time.astimezone(UTC).isoformat()
            if getattr(result_info, "finish_time", None):
                updated_at = result_info.finish_time.astimezone(UTC).isoformat()
    elif status_name == "not_found":
        status, error = "failed", "任务不存在"

    return JobOut(
        id=job_id,
        kind=kind,
        status=status,
        progress=progress,
        error=error,
        result_ref=result_ref,
        created_at=created_at,
        updated_at=updated_at,
    )


async def get_job_out(job_id: str) -> JobOut | None:
    client = _sync_redis()
    meta = cast(dict[str, Any], client.hgetall(ARQ_JOBS_META_KEY_FMT.format(job_id=job_id))) or {}
    kind = str(meta.get("kind") or "")
    created_at = str(meta.get("created_at") or datetime.now(UTC).isoformat())

    pool = await _arq_pool()
    queue = str(meta.get("queue") or "")
    if not queue:
        queue = (
            get_settings().arq_backtest_queue_name if kind.startswith("backtest.") else get_settings().arq_queue_name
        )
    job = Job(job_id, redis=pool, _queue_name=queue)
    st = await job.status()
    if st == JobStatus.not_found and not meta:
        return None
    info = await job.result_info()
    if not kind and info is not None:
        fn = getattr(info, "function", "") or ""
        if fn == "run_ops_job":
            ops_id = ""
            if info.args:
                ops_id = str(info.args[0])
            kind = f"ops.{ops_id}" if ops_id else ""
        else:
            for k, fname in {**SCREENER_FUNCS, **BACKTEST_FUNCS}.items():
                if fname == fn:
                    kind = k
                    break
    if not kind:
        return None
    return _job_out_from_arq(
        job_id=job_id,
        kind=kind,
        status_name=st.name if hasattr(st, "name") else str(st),
        result_info=info,
        created_at_fallback=created_at,
    )


async def get_ops_job_out(job_id: str) -> JobOut | None:
    out = await get_job_out(job_id)
    if out is None or not out.kind.startswith("ops."):
        return None
    return out


async def list_job_outs(*, limit: int = 50) -> list[JobOut]:
    client = _sync_redis()
    ids = cast(list[str], client.zrevrange(ARQ_JOBS_RECENT_ZSET, 0, max(limit - 1, 0))) or []
    out: list[JobOut] = []
    for arq_id in ids:
        row = await get_job_out(str(arq_id))
        if row is not None:
            out.append(row)
    return out[:limit]


async def list_ops_job_outs(*, limit: int = 50) -> list[JobOut]:
    rows = await list_job_outs(limit=limit * 2)
    return [r for r in rows if r.kind.startswith("ops.")][:limit]


def auto_arq_id(task_id: str) -> str:
    return f"auto:{task_id}"


async def enqueue_auto_task(task_id: str) -> str:
    """以稳定 job id 入队自动任务；进行中则直接复用，避免重复执行。"""
    stable_id = auto_arq_id(task_id)
    pool = await _arq_pool()
    settings = get_settings()
    job_probe = Job(stable_id, redis=pool, _queue_name=settings.arq_queue_name)
    st = await job_probe.status()
    if st in _IN_FLIGHT:
        return stable_id
    if st in {JobStatus.complete, JobStatus.not_found}:
        await _clear_arq_job_keys(pool, stable_id)
    job = await pool.enqueue_job(
        "run_auto_schedule_task",
        task_id,
        _job_id=stable_id,
        _queue_name=settings.arq_queue_name,
    )
    if job is None:
        raise RuntimeError(f"enqueue 失败：{task_id}")
    return job.job_id


def enqueue_auto_task_sync(task_id: str) -> str:
    return asyncio.run(enqueue_auto_task(task_id))

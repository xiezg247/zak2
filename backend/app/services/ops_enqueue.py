"""Ops ARQ enqueue、旁路索引与 JobOut 映射。"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

import redis
from arq import create_pool
from arq.connections import ArqRedis, RedisSettings
from arq.jobs import Job, JobStatus

from app.core.redis_keys import (
    ARQ_OPS_META_KEY_FMT,
    ARQ_OPS_RECENT_MAX,
    ARQ_OPS_RECENT_ZSET,
)
from app.core.settings import get_settings
from app.schemas.screener import JobOut

_pool: ArqRedis | None = None


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


def _index_ops_job(
    client: redis.Redis,
    *,
    arq_id: str,
    ops_job_id: str,
    user_id: str | None,
    created_at: str,
    score_ms: int,
) -> None:
    meta_key = ARQ_OPS_META_KEY_FMT.format(job_id=arq_id)
    client.zadd(ARQ_OPS_RECENT_ZSET, {arq_id: score_ms})
    client.hset(
        meta_key,
        mapping={
            "kind": f"ops.{ops_job_id}",
            "ops_job_id": ops_job_id,
            "created_at": created_at,
            "user_id": user_id or "",
        },
    )
    client.zremrangebyrank(ARQ_OPS_RECENT_ZSET, 0, -(ARQ_OPS_RECENT_MAX + 1))


async def enqueue_ops_job(
    ops_job_id: str,
    *,
    user_id: str | None = None,
    force: bool = False,
) -> str:
    pool = await _arq_pool()
    settings = get_settings()
    job = await pool.enqueue_job(
        "run_ops_job",
        ops_job_id,
        user_id=user_id,
        force=force,
        _queue_name=settings.arq_queue_name,
    )
    if job is None:
        raise RuntimeError(f"enqueue 失败（可能重复 job id）：{ops_job_id}")
    now = datetime.now(UTC)
    created_at = now.isoformat()
    score_ms = int(now.timestamp() * 1000)
    _index_ops_job(
        _sync_redis(),
        arq_id=job.job_id,
        ops_job_id=ops_job_id,
        user_id=user_id,
        created_at=created_at,
        score_ms=score_ms,
    )
    return job.job_id


def enqueue_ops_job_sync(
    ops_job_id: str,
    *,
    user_id: str | None = None,
    force: bool = False,
) -> str:
    return asyncio.run(enqueue_ops_job(ops_job_id, user_id=user_id, force=force))


def _job_out_from_arq(
    *,
    job_id: str,
    ops_job_id: str,
    status_name: str,
    result_info: Any | None,
    created_at_fallback: str,
) -> JobOut:
    kind = f"ops.{ops_job_id}"
    created_at = created_at_fallback
    updated_at = created_at_fallback
    status = "pending"
    progress = 0.0
    error: str | None = None
    result_ref: str | None = None

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
                ok = True if ops_job_id == "purge_stale_cache" else bool(raw.get("success", True))
                msg = str(raw.get("message") or "完成")
                if raw.get("skipped") or ok:
                    status, result_ref = "success", msg
                else:
                    status, error = "failed", msg
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


async def get_ops_job_out(job_id: str) -> JobOut | None:
    client = _sync_redis()
    meta_key = ARQ_OPS_META_KEY_FMT.format(job_id=job_id)
    meta = client.hgetall(meta_key) or {}
    ops_job_id = str(meta.get("ops_job_id") or "")
    created_at = str(meta.get("created_at") or datetime.now(UTC).isoformat())

    pool = await _arq_pool()
    job = Job(job_id, redis=pool, _queue_name=get_settings().arq_queue_name)
    st = await job.status()
    if st == JobStatus.not_found and not meta:
        return None
    info = await job.result_info()
    if not ops_job_id and info is not None:
        ops_job_id = str((info.kwargs or {}).get("ops_job_id") or "")
        if not ops_job_id and info.args:
            ops_job_id = str(info.args[0])
    if not ops_job_id:
        return None
    return _job_out_from_arq(
        job_id=job_id,
        ops_job_id=ops_job_id,
        status_name=st.name if hasattr(st, "name") else str(st),
        result_info=info,
        created_at_fallback=created_at,
    )


async def list_ops_job_outs(*, limit: int = 50) -> list[JobOut]:
    client = _sync_redis()
    ids = client.zrevrange(ARQ_OPS_RECENT_ZSET, 0, max(limit - 1, 0)) or []
    out: list[JobOut] = []
    for arq_id in ids:
        row = await get_ops_job_out(str(arq_id))
        if row is not None:
            out.append(row)
    return out[:limit]

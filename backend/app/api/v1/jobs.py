from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_current_user
from app.jobs.store import job_store
from app.models.user import User
from app.schemas.screener import JobOut
from app.services.ops_enqueue import get_ops_job_out, list_ops_job_outs

router = APIRouter(prefix="/jobs", tags=["jobs"])


def _to_out(job) -> JobOut:  # type: ignore[no-untyped-def]
    return JobOut(
        id=job.id,
        kind=job.kind,
        status=job.status,
        progress=job.progress,
        error=job.error,
        result_ref=job.result_ref,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


async def _resolve_job(job_id: str) -> JobOut | None:
    job = job_store.get(job_id)
    if job:
        return _to_out(job)
    return await get_ops_job_out(job_id)


async def _list_merged(*, limit: int = 50) -> list[JobOut]:
    mem = [_to_out(j) for j in job_store.list_recent(limit=limit)]
    ops = await list_ops_job_outs(limit=limit)
    merged = sorted(mem + ops, key=lambda j: j.created_at, reverse=True)
    return merged[:limit]


@router.get("", response_model=list[JobOut])
async def list_jobs(user: User = Depends(get_current_user)) -> list[JobOut]:
    _ = user
    return await _list_merged(limit=50)


@router.get("/{job_id}", response_model=JobOut)
async def get_job(job_id: str, user: User = Depends(get_current_user)) -> JobOut:
    _ = user
    job = await _resolve_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")
    return job

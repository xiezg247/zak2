from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_current_user
from app.jobs.store import job_store
from app.models.user import User
from app.schemas.screener import JobOut

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


@router.get("", response_model=list[JobOut])
def list_jobs(user: User = Depends(get_current_user)) -> list[JobOut]:
    _ = user
    return [_to_out(j) for j in job_store.list_recent()]


@router.get("/{job_id}", response_model=JobOut)
def get_job(job_id: str, user: User = Depends(get_current_user)) -> JobOut:
    _ = user
    job = job_store.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")
    return _to_out(job)

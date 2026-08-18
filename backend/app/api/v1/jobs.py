from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.screener import JobOut
from app.services.ops.arq_jobs import get_job_out, list_job_outs

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("", response_model=ApiResponse[list[JobOut]])
async def list_jobs(user: User = Depends(get_current_user)) -> ApiResponse[list[JobOut]]:
    _ = user
    return ApiResponse(data=await list_job_outs(limit=50))


@router.get("/{job_id}", response_model=ApiResponse[JobOut])
async def get_job(job_id: str, user: User = Depends(get_current_user)) -> ApiResponse[JobOut]:
    _ = user
    job = await get_job_out(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")
    return ApiResponse(data=job)

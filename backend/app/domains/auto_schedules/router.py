"""自动任务域：薄路由，仅依赖注入并转发 AutoScheduleService。"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.db import get_db
from app.domains.auto_schedules.schemas import (
    AutoScheduleCreate,
    AutoScheduleEnabledPatch,
    AutoScheduleListOut,
    AutoScheduleOut,
    AutoScheduleUpdate,
)
from app.domains.auto_schedules.service import AutoScheduleService
from app.models.user import User
from app.schemas.common import ApiResponse, OkOut

router = APIRouter(prefix="/auto-schedules", tags=["auto-schedules"])


@router.get("", response_model=ApiResponse[AutoScheduleListOut])
def list_auto_schedules(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[AutoScheduleListOut]:
    return ApiResponse(data=AutoScheduleService.list(db, str(user.id)))


@router.post("", response_model=ApiResponse[AutoScheduleOut])
def create_auto_schedule(
    body: AutoScheduleCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[AutoScheduleOut]:
    return ApiResponse(data=AutoScheduleService.create(db, str(user.id), body))


@router.patch("/{task_id}", response_model=ApiResponse[AutoScheduleOut])
def update_auto_schedule(
    task_id: int,
    body: AutoScheduleUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[AutoScheduleOut]:
    return ApiResponse(data=AutoScheduleService.update(db, str(user.id), task_id, body))


@router.patch("/{task_id}/enabled", response_model=ApiResponse[AutoScheduleOut])
def set_auto_schedule_enabled(
    task_id: int,
    body: AutoScheduleEnabledPatch,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[AutoScheduleOut]:
    return ApiResponse(data=AutoScheduleService.set_enabled(db, str(user.id), task_id, body.enabled))


@router.delete("/{task_id}", response_model=ApiResponse[OkOut])
def delete_auto_schedule(
    task_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[OkOut]:
    AutoScheduleService.delete(db, str(user.id), task_id)
    return ApiResponse(data=OkOut())

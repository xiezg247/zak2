"""自动任务：CRUD + 启用/暂停。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.db import get_db
from app.models.auto_schedule import AutoSchedule
from app.models.user import User
from app.repositories.auto_schedule import AutoScheduleRepository
from app.schemas.auto_schedule import (
    AutoScheduleCreate,
    AutoScheduleEnabledPatch,
    AutoScheduleListOut,
    AutoScheduleOut,
    AutoScheduleUpdate,
)
from app.schemas.common import ApiResponse, OkOut
from app.services.ops.auto_schedule import validate_task_input
from app.services.ops.auto_schedule_time import parse_times

router = APIRouter(prefix="/auto-schedules", tags=["auto-schedules"])


def _get_owned(
    db: Session, user_id: str, task_id: int
) -> tuple[AutoScheduleRepository, AutoSchedule]:
    repo = AutoScheduleRepository(db, user_id)
    task = repo.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    return repo, task


@router.get("", response_model=ApiResponse[AutoScheduleListOut])
def list_auto_schedules(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[AutoScheduleListOut]:
    repo = AutoScheduleRepository(db, str(user.id))
    tasks = repo.list_all()
    return ApiResponse(data=AutoScheduleListOut(items=[repo.to_out(t) for t in tasks]))


@router.post("", response_model=ApiResponse[AutoScheduleOut])
def create_auto_schedule(
    body: AutoScheduleCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[AutoScheduleOut]:
    repo = AutoScheduleRepository(db, str(user.id))
    try:
        validate_task_input(
            name=body.name,
            recipe_id=body.recipe_id,
            days_of_week=body.days_of_week,
            times=body.times,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    task = repo.create_task(
        name=body.name.strip(),
        recipe_id=body.recipe_id,
        days_of_week=body.days_of_week.strip().lower(),
        times=parse_times(body.times),
    )
    return ApiResponse(data=repo.to_out(task))


@router.patch("/{task_id}", response_model=ApiResponse[AutoScheduleOut])
def update_auto_schedule(
    task_id: int,
    body: AutoScheduleUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[AutoScheduleOut]:
    repo, task = _get_owned(db, str(user.id), task_id)
    values = body.model_dump(exclude_none=True)
    if not values:
        raise HTTPException(status_code=400, detail="没有需要更新的字段")
    try:
        validate_task_input(
            name=values.get("name", task.name),
            recipe_id=values.get("recipe_id", task.recipe_id),
            days_of_week=values.get("days_of_week", task.days_of_week),
            times=values.get("times", list(task.times or [])),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if "name" in values:
        values["name"] = str(values["name"]).strip()
    if "days_of_week" in values:
        values["days_of_week"] = str(values["days_of_week"]).strip().lower()
    if "times" in values:
        values["times"] = parse_times(values["times"])
    updated = repo.update_task(task_id, values)
    if updated is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    return ApiResponse(data=repo.to_out(updated))


@router.patch("/{task_id}/enabled", response_model=ApiResponse[AutoScheduleOut])
def set_auto_schedule_enabled(
    task_id: int,
    body: AutoScheduleEnabledPatch,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[AutoScheduleOut]:
    repo, _ = _get_owned(db, str(user.id), task_id)
    updated = repo.update_task(task_id, {"enabled": body.enabled})
    if updated is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    return ApiResponse(data=repo.to_out(updated))


@router.delete("/{task_id}", response_model=ApiResponse[OkOut])
def delete_auto_schedule(
    task_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[OkOut]:
    repo, _ = _get_owned(db, str(user.id), task_id)
    repo.delete(task_id)
    return ApiResponse(data=OkOut())

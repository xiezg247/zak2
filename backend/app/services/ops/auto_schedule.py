"""自动任务：校验、执行与分钟级轮询。"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.auto_schedule import AutoSchedule
from app.repositories import screener as screener_repo
from app.repositories.auto_schedule import AutoScheduleRepository
from app.schemas.ops import SyncResult
from app.schemas.screener import RecipeRunRequest
from app.services.notify import delivery as notify_delivery
from app.services.ops.arq_jobs import enqueue_auto_task_sync
from app.services.ops.auto_schedule_time import matches_now, parse_days_of_week, parse_times
from app.services.screener.engine import run_recipe_screen
from app.services.screener.presets import get_builtin_recipe

logger = logging.getLogger(__name__)

_META_MESSAGE_MAX = 200


def _now_str() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")


def validate_task_input(*, name: str, recipe_id: str, days_of_week: str, times: list[str]) -> None:
    """校验创建/编辑入参；非法抛 ValueError。"""
    if not name.strip():
        raise ValueError("任务名称不能为空")
    recipe = get_builtin_recipe(recipe_id)
    if recipe is None or not recipe.implemented:
        raise ValueError(f"未知或未实现的配方：{recipe_id}")
    parse_days_of_week(days_of_week)
    parse_times(times)


def _record_run(db: Session, task: AutoSchedule, *, message: str, success: bool) -> None:
    task.last_run_at = _now_str()
    task.last_message = str(message)[:_META_MESSAGE_MAX]
    task.last_success = success
    db.commit()


def _notify_result(db: Session, task: AutoSchedule, result: dict[str, Any], run_id: str) -> None:
    from app.services.ops.auto_screen import _format_screen_lines

    text = _format_screen_lines(f"自动任务「{task.name}」", result, run_id)
    notify_delivery.deliver_text(
        db,
        user_id=task.user_id,
        event_type=f"auto_schedule.{task.id}",
        title=f"自动任务：{task.name}",
        text=text,
    )


def run_task(db: Session, task_id: int) -> SyncResult:
    """ARQ worker 执行体：跑配方选股、写历史、更新任务 meta、推送。"""
    repo = AutoScheduleRepository(db, "")
    task = repo.get_any(task_id)
    if task is None:
        return SyncResult(success=False, skipped=True, message="任务不存在")
    if not task.enabled:
        return SyncResult(success=False, skipped=True, message="任务已停用")

    try:
        recipe = get_builtin_recipe(task.recipe_id)
        if recipe is None or not recipe.implemented:
            raise ValueError(f"未知或未实现的配方：{task.recipe_id}")
        req = RecipeRunRequest(recipe_id=task.recipe_id)
        prev = screener_repo.ScreenerRunRepository(db, task.user_id).latest_run_symbols()
        result = run_recipe_screen(req, previous_symbols=prev, db=db, user_id=task.user_id)
        run = screener_repo.ScreenerRunRepository(db, task.user_id).save_run(
            condition=str(result.get("condition") or task.name),
            source="auto_schedule",
            result={**result, "config": {**(result.get("config") or {}), "trigger": f"auto_schedule.{task.id}"}},
        )
    except HTTPException as exc:
        _record_run(db, task, message=str(exc.detail), success=False)
        return SyncResult(success=False, message=str(exc.detail))
    except Exception as exc:
        logger.exception("自动任务执行失败：task=%s", task_id)
        _record_run(db, task, message=str(exc), success=False)
        return SyncResult(success=False, message=str(exc))

    message = f"{task.name}完成：{result.get('condition')} 命中 {result.get('row_count')} 只（run={run.id}）"
    _record_run(db, task, message=message, success=True)
    try:
        _notify_result(db, task, result, run.id)
    except Exception:
        logger.warning("自动任务推送失败：task=%s", task.id, exc_info=True)
    return SyncResult(
        success=True,
        message=message,
        extra={"run_id": run.id, "row_count": result.get("row_count")},
    )


def poll_due_tasks(db: Session, now: datetime) -> list[dict[str, str]]:
    """扫描启用任务，命中当前时刻者入队 ARQ；返回 [{task_id, arq_id}]。"""
    tasks = db.scalars(select(AutoSchedule).where(AutoSchedule.enabled.is_(True))).all()
    due: list[AutoSchedule] = []
    for task in tasks:
        if not task.enabled:
            continue
        try:
            days = parse_days_of_week(task.days_of_week)
            times = parse_times(list(task.times or []))
        except ValueError:
            logger.warning("自动任务配置非法，跳过：task=%s", task.id)
            continue
        if matches_now(days, times, now):
            due.append(task)
    enqueued: list[dict[str, str]] = []
    for task in due:
        try:
            arq_id = enqueue_auto_task_sync(str(task.id))
        except Exception:
            logger.exception("自动任务入队失败：task=%s", task.id)
            continue
        enqueued.append({"task_id": str(task.id), "arq_id": arq_id})
    return enqueued

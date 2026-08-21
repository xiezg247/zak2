"""自动任务域：仓库层（app.auto_schedule）。"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.domains.auto_schedules.schemas import AutoScheduleOut
from app.models.auto_schedule import AutoSchedule
from app.repositories.base import BaseRepository


def _now_str() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")


class AutoScheduleRepository(BaseRepository[AutoSchedule]):
    model = AutoSchedule
    order_by = (AutoSchedule.created_at,)

    def get_any(self, key: int) -> AutoSchedule | None:
        """跨用户读取（供 worker 按任务 id 执行）。"""
        return self.db.get(AutoSchedule, key)

    def to_out(self, task: AutoSchedule) -> AutoScheduleOut:
        return AutoScheduleOut(
            id=task.id,
            name=task.name,
            recipe_id=task.recipe_id,
            days_of_week=task.days_of_week,
            times=list(task.times or []),
            enabled=task.enabled,
            last_run_at=task.last_run_at,
            last_message=task.last_message,
            last_success=task.last_success,
            created_at=task.created_at,
            updated_at=task.updated_at,
        )

    def create_task(
        self,
        *,
        name: str,
        recipe_id: str,
        days_of_week: str,
        times: list[str],
        enabled: bool = True,
    ) -> AutoSchedule:
        now = _now_str()
        return self.create(
            name=name,
            recipe_id=recipe_id,
            days_of_week=days_of_week,
            times=times,
            enabled=enabled,
            created_at=now,
            updated_at=now,
        )

    def update_task(self, key: int, values: dict[str, Any]) -> AutoSchedule | None:
        values = dict(values)
        if values:
            values["updated_at"] = _now_str()
        return self.update(key, **values)

"""兼容壳：模型已迁至 app.domains.auto_schedules.schemas。"""

from app.domains.auto_schedules.schemas import (
    AutoScheduleCreate,
    AutoScheduleEnabledPatch,
    AutoScheduleListOut,
    AutoScheduleOut,
    AutoScheduleUpdate,
)

__all__ = [
    "AutoScheduleCreate",
    "AutoScheduleUpdate",
    "AutoScheduleEnabledPatch",
    "AutoScheduleOut",
    "AutoScheduleListOut",
]

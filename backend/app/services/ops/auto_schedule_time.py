"""兼容壳：实现已迁至 app.domains.auto_schedules.auto_schedule_time。"""

from __future__ import annotations

import sys

from app.domains.auto_schedules import auto_schedule_time as _impl

sys.modules[__name__] = _impl

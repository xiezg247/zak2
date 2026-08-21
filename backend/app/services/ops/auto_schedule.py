"""兼容壳：实现已迁至 app.domains.auto_schedules.service。"""

from __future__ import annotations

import sys

from app.domains.auto_schedules import service as _impl

sys.modules[__name__] = _impl

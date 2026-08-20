"""兼容壳：实现已迁至 app.domains.screener.hard_filters。"""

from __future__ import annotations

import sys

from app.domains.screener import hard_filters as _impl

sys.modules[__name__] = _impl

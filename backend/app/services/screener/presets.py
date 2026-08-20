"""兼容壳：实现已迁至 app.domains.screener.presets。"""

from __future__ import annotations

import sys

from app.domains.screener import presets as _impl

sys.modules[__name__] = _impl

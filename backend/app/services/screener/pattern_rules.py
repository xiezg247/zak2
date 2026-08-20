"""兼容壳：实现已迁至 app.domains.screener.pattern_rules。"""

from __future__ import annotations

import sys

from app.domains.screener import pattern_rules as _impl

sys.modules[__name__] = _impl

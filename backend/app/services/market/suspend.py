"""兼容壳：实现已迁至 app.domains.market.suspend。"""

from __future__ import annotations

import sys

from app.domains.market import suspend as _impl

sys.modules[__name__] = _impl

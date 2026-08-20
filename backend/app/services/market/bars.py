"""兼容壳：实现已迁至 app.domains.market.bars。"""

from __future__ import annotations

import sys

from app.domains.market import bars as _impl

sys.modules[__name__] = _impl

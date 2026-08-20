"""兼容壳：实现已迁至 app.domains.market.stock_industry。"""

from __future__ import annotations

import sys

from app.domains.market import stock_industry as _impl

sys.modules[__name__] = _impl

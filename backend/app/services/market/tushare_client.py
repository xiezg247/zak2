"""兼容壳：实现已迁至 app.domains.market.tushare_client。"""

from __future__ import annotations

import sys

from app.domains.market import tushare_client as _impl

sys.modules[__name__] = _impl

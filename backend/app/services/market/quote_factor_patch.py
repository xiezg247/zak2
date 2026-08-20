"""兼容壳：实现已迁至 app.domains.market.quote_factor_patch。"""

from __future__ import annotations

import sys

from app.domains.market import quote_factor_patch as _impl

sys.modules[__name__] = _impl

"""兼容壳：实现已迁至 app.domains.market.limit_list_store。"""

from __future__ import annotations

import sys

from app.domains.market import limit_list_store as _impl

sys.modules[__name__] = _impl

"""兼容壳：实现已迁至 app.domains.market.quote_notify_hub。"""

from __future__ import annotations

import sys

from app.domains.market import quote_notify_hub as _impl

sys.modules[__name__] = _impl

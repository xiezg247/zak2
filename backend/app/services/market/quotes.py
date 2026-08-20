"""兼容壳：实现已迁至 app.domains.market.quotes。"""

from __future__ import annotations

import sys

from app.domains.market import quotes as _impl

sys.modules[__name__] = _impl

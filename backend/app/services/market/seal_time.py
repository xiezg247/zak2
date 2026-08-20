"""兼容壳：实现已迁至 app.domains.market.seal_time。"""

from __future__ import annotations

import sys

from app.domains.market import seal_time as _impl

sys.modules[__name__] = _impl

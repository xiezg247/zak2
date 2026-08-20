"""兼容壳：实现已迁至 app.domains.market.sector。"""

from __future__ import annotations

import sys

from app.domains.market import sector as _impl

sys.modules[__name__] = _impl

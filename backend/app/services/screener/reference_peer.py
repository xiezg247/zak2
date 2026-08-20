"""兼容壳：实现已迁至 app.domains.screener.reference_peer。"""

from __future__ import annotations

import sys

from app.domains.screener import reference_peer as _impl

sys.modules[__name__] = _impl

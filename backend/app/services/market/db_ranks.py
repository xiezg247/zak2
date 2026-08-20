"""兼容壳：实现已迁至 app.domains.market.db_ranks。"""

from __future__ import annotations

import sys

from app.domains.market import db_ranks as _impl

sys.modules[__name__] = _impl

"""兼容壳：实现已迁至 app.domains.screener.recipe_weights。"""

from __future__ import annotations

import sys

from app.domains.screener import recipe_weights as _impl

sys.modules[__name__] = _impl

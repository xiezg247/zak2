"""兼容壳：实现已迁至 app.domains.screener.resonance_screen。"""

from __future__ import annotations

import sys

from app.domains.screener import resonance_screen as _impl

sys.modules[__name__] = _impl

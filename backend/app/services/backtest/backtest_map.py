"""兼容壳：实现已迁至 app.domains.backtest.backtest_map。"""

from __future__ import annotations

import sys

from app.domains.backtest import backtest_map as _impl

sys.modules[__name__] = _impl

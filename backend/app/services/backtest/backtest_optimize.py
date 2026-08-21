"""兼容壳：实现已迁至 app.domains.backtest.backtest_optimize。"""

from __future__ import annotations

import sys

from app.domains.backtest import backtest_optimize as _impl

sys.modules[__name__] = _impl

"""兼容壳：实现已迁至 app.domains.backtest.backtest_vnpy。"""

from __future__ import annotations

import sys

from app.domains.backtest import backtest_vnpy as _impl

sys.modules[__name__] = _impl

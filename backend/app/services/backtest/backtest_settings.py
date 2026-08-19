"""按策略组装 CTA setting 与 K 线门槛。"""

from __future__ import annotations

from typing import Any

from app.schemas.backtest import BacktestRunRequest


def build_strategy_setting(req: BacktestRunRequest) -> dict[str, Any]:
    base: dict[str, Any] = {
        "fast_window": req.fast_window,
        "slow_window": req.slow_window,
        "trade_volume": 100,
    }
    if req.strategy == "trend_ma":
        base.update(
            {
                "adx_period": req.adx_period,
                "adx_threshold": req.adx_threshold,
                "trailing_stop_pct": req.trailing_stop_pct,
            }
        )
    elif req.strategy == "medium_swing":
        base.update(
            {
                "fast_period": req.fast_window,
                "slow_period": req.slow_window,
                "signal_period": req.signal_period,
                "trend_ma_window": req.trend_ma_window,
            }
        )
    return base


def min_bars_for_request(req: BacktestRunRequest) -> int:
    base = 30
    if req.strategy == "trend_ma":
        base = max(30, req.slow_window + req.adx_period * 2 + 5)
    elif req.strategy == "medium_swing":
        base = max(30, req.slow_window * 2 + 2, req.trend_ma_window + 5)
    if req.interval == "1m":
        return max(base, 100)
    return base

"""按策略组装 CTA setting 与 K 线门槛。"""

from __future__ import annotations

from app.schemas.backtest import BacktestRunRequest


def build_strategy_setting(req: BacktestRunRequest) -> dict:
    base = {
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
    return base


def min_bars_for_request(req: BacktestRunRequest) -> int:
    if req.strategy == "trend_ma":
        base = max(30, req.slow_window + req.adx_period * 2 + 5)
    else:
        base = 30
    if req.interval == "1m":
        return max(base, 100)
    return base

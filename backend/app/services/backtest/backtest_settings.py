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
    elif req.strategy == "donchian":
        base.pop("fast_window", None)
        base.pop("slow_window", None)
        base.update({"entry_window": req.entry_window, "exit_window": req.exit_window})
    elif req.strategy == "rsi_reversal":
        base.pop("fast_window", None)
        base.pop("slow_window", None)
        base.update(
            {
                "rsi_period": req.rsi_period,
                "oversold": req.oversold,
                "overbought": req.overbought,
            }
        )
    elif req.strategy == "bollinger":
        base.pop("fast_window", None)
        base.pop("slow_window", None)
        base.update({"boll_period": req.boll_period, "boll_dev": req.boll_dev})
    elif req.strategy == "ma_band":
        base.pop("fast_window", None)
        base.pop("slow_window", None)
        base.update(
            {
                "ma_fast": req.ma_fast,
                "ma_mid": req.ma_mid,
                "ma_slow": req.ma_slow,
                "ma_long": req.ma_long,
            }
        )
    elif req.strategy == "atr_breakout":
        base.pop("fast_window", None)
        base.pop("slow_window", None)
        base.update(
            {
                "channel_period": req.channel_period,
                "atr_period": req.atr_period,
                "atr_mult": req.atr_mult,
            }
        )
    return base


def min_bars_for_request(req: BacktestRunRequest) -> int:
    base = 30
    if req.strategy == "trend_ma":
        base = max(30, req.slow_window + req.adx_period * 2 + 5)
    elif req.strategy == "medium_swing":
        base = max(30, req.slow_window * 2 + 2, req.trend_ma_window + 5)
    elif req.strategy == "donchian":
        base = max(30, req.entry_window + 2)
    elif req.strategy == "rsi_reversal":
        base = max(30, req.rsi_period * 2 + 2)
    elif req.strategy == "bollinger":
        base = max(30, req.boll_period + 2)
    elif req.strategy == "ma_band":
        base = max(30, req.ma_long + 2)
    elif req.strategy == "atr_breakout":
        base = max(30, req.channel_period + 2, req.atr_period * 2 + 2)
    if req.interval == "1m":
        return max(base, 100)
    return base

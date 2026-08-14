"""回测策略元数据与历史薄引擎残留（生产已切 vnpy）。"""

from __future__ import annotations

from app.services.backtest_bars import Bar, load_daily_bars

__all__ = [
    "STRATEGIES",
    "PROFILES",
    "Bar",
    "load_daily_bars",
    "_sma",
]

STRATEGIES = (
    {
        "id": "double_ma",
        "name": "双均线",
        "interval": "d",
        "description": "vnpy CTA：快线上穿慢线买入、下穿卖出；整手 100 股；仅做多；支持 d/1m",
        "implemented": True,
        "engine": "vnpy",
    },
    {
        "id": "trend_ma",
        "name": "趋势双均线（ADX）",
        "interval": "d",
        "description": "金叉+ADX过滤买入；死叉/破慢线/追踪止损卖出；整手 T+1；支持 d/1m",
        "implemented": True,
        "engine": "vnpy",
    },
)

PROFILES = (
    {"profile_id": "ultra_short", "name": "极致短线", "description": "打板/半路，持仓短", "fast_window": 3, "slow_window": 8, "capital": 100_000},
    {"profile_id": "short_swing", "name": "短线波段", "description": "放量突破为主", "fast_window": 5, "slow_window": 20, "capital": 100_000},
    {"profile_id": "medium_watch", "name": "中线观察", "description": "趋势跟踪辅助", "fast_window": 10, "slow_window": 30, "capital": 100_000},
    {"profile_id": "trend", "name": "趋势", "description": "均线趋势，持仓更长", "fast_window": 20, "slow_window": 60, "capital": 100_000},
)


def _sma(values: list[float], window: int) -> list[float | None]:
    out: list[float | None] = [None] * len(values)
    if window <= 0:
        return out
    s = 0.0
    for i, v in enumerate(values):
        s += v
        if i >= window:
            s -= values[i - window]
        if i >= window - 1:
            out[i] = s / window
    return out

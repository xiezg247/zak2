"""策略 id → CTA 类（惰性加载，避免 API 进程强依赖 vnpy）。"""

from __future__ import annotations


def get_strategy_class(strategy_id: str) -> type:
    if strategy_id == "double_ma":
        from app.strategies.cta.double_ma import DoubleMaStrategy

        return DoubleMaStrategy
    if strategy_id == "trend_ma":
        from app.strategies.cta.trend_ma import TrendMaStrategy

        return TrendMaStrategy
    raise KeyError(f"未知策略：{strategy_id}")

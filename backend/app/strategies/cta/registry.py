"""策略 id → CTA 类（惰性加载，避免 API 进程强依赖 vnpy）。"""

from __future__ import annotations


def get_strategy_class(strategy_id: str) -> type:
    if strategy_id == "double_ma":
        from app.strategies.cta.double_ma import DoubleMaStrategy

        return DoubleMaStrategy
    if strategy_id == "trend_ma":
        from app.strategies.cta.trend_ma import TrendMaStrategy

        return TrendMaStrategy
    if strategy_id == "medium_swing":
        from app.strategies.cta.medium_swing import MediumSwingStrategy

        return MediumSwingStrategy
    if strategy_id == "donchian":
        from app.strategies.cta.donchian import DonchianStrategy

        return DonchianStrategy
    if strategy_id == "rsi_reversal":
        from app.strategies.cta.rsi_reversal import RsiReversalStrategy

        return RsiReversalStrategy
    if strategy_id == "bollinger":
        from app.strategies.cta.bollinger import BollingerStrategy

        return BollingerStrategy
    if strategy_id == "ma_band":
        from app.strategies.cta.ma_band import MaBandStrategy

        return MaBandStrategy
    if strategy_id == "atr_breakout":
        from app.strategies.cta.atr_breakout import AtrBreakoutStrategy

        return AtrBreakoutStrategy
    raise KeyError(f"未知策略：{strategy_id}")

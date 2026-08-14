"""策略 id → CTA 类。"""

from __future__ import annotations

from app.strategies.cta.double_ma import DoubleMaStrategy

_REGISTRY: dict[str, type] = {
    "double_ma": DoubleMaStrategy,
}


def get_strategy_class(strategy_id: str) -> type:
    cls = _REGISTRY.get(strategy_id)
    if cls is None:
        raise KeyError(f"未知策略：{strategy_id}")
    return cls

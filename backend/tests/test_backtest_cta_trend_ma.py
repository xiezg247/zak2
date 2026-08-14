import pytest

pytest.importorskip("vnpy_ctastrategy")


@pytest.mark.vnpy
def test_registry_trend_ma():
    from app.strategies.cta.registry import get_strategy_class

    assert get_strategy_class("trend_ma").__name__ == "TrendMaStrategy"

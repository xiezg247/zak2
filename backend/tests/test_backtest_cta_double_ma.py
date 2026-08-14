import pytest

pytest.importorskip("vnpy_ctastrategy")


@pytest.mark.vnpy
def test_registry_double_ma():
    from app.strategies.cta.registry import get_strategy_class

    cls = get_strategy_class("double_ma")
    assert cls.__name__ == "DoubleMaStrategy"


@pytest.mark.vnpy
def test_round_volume():
    from app.strategies.cta.ashare_template import AShareCtaTemplate

    # 不实例化引擎：直接测静态逻辑
    assert AShareCtaTemplate.round_volume(AShareCtaTemplate, 150) == 100
    assert AShareCtaTemplate.round_volume(AShareCtaTemplate, 50) == 0
    assert AShareCtaTemplate.round_volume(AShareCtaTemplate, 200) == 200

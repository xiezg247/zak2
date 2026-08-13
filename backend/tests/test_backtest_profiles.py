from app.schemas.backtest import StrategyProfileOut
from app.services.backtest_engine import PROFILES


def test_profiles_have_window_and_capital() -> None:
    assert len(PROFILES) >= 4
    for raw in PROFILES:
        p = StrategyProfileOut.model_validate(raw)
        assert 2 <= p.fast_window < p.slow_window <= 250
        assert p.capital > 0

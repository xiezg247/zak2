from app.domains.backtest.backtest_engine import PROFILES
from app.domains.backtest.schemas import StrategyProfileOut


def test_profiles_have_window_and_capital() -> None:
    assert len(PROFILES) >= 4
    for raw in PROFILES:
        p = StrategyProfileOut.model_validate(raw)
        assert 2 <= p.fast_window < p.slow_window <= 250
        assert p.capital > 0

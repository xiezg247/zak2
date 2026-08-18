from app.services.backtest.backtest_engine import PROFILES, STRATEGIES, _sma


def test_sma() -> None:
    vals = [1.0, 2.0, 3.0, 4.0, 5.0]
    out = _sma(vals, 3)
    assert out[0] is None and out[1] is None
    assert abs((out[2] or 0) - 2.0) < 1e-9
    assert abs((out[4] or 0) - 4.0) < 1e-9


def test_strategies_engine_vnpy() -> None:
    assert STRATEGIES[0]["engine"] == "vnpy"
    assert len(PROFILES) >= 1

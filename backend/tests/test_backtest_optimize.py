import pytest

from app.services.backtest.backtest_optimize import expand_ma_grid, pick_best


def test_expand_filters_fast_ge_slow():
    combos = expand_ma_grid({"fast_window": [5, 20], "slow_window": [10, 20]})
    assert {"fast_window": 5, "slow_window": 10} in combos
    assert {"fast_window": 20, "slow_window": 10} not in combos


def test_expand_rejects_over_64():
    with pytest.raises(ValueError, match="64"):
        expand_ma_grid(
            {
                "fast_window": list(range(2, 12)),
                "slow_window": list(range(20, 30)),
            }
        )


def test_pick_best_sharpe():
    best = pick_best(
        [{"sharpe_ratio": 0.1}, {"sharpe_ratio": 1.2}, {"sharpe_ratio": None}],
        objective="sharpe_ratio",
    )
    assert best is not None
    assert best["sharpe_ratio"] == 1.2

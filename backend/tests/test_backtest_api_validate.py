from app.services.backtest.backtest_optimize import expand_ma_grid


def test_expand_over_64_message():
    try:
        expand_ma_grid(
            {
                "fast_window": list(range(2, 12)),
                "slow_window": list(range(20, 30)),
            }
        )
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert "64" in str(exc)


def test_validate_helper_semantics():
    from app.api.v1 import backtest as api

    try:
        api._validate_ma_windows("double_ma", 20, 10)
        raise AssertionError("expected HTTPException")
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 400


def test_validate_helper_skips_non_ma_strategy():
    from app.api.v1 import backtest as api

    api._validate_ma_windows("bollinger", 20, 10)

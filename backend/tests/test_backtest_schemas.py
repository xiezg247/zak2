from app.schemas.backtest import BacktestRunRequest, OptimizeBacktestRequest


def test_run_request_fee_defaults():
    r = BacktestRunRequest(vt_symbol="600519.SSE")
    assert r.rate == 0.00045
    assert r.slippage == 0.0
    assert r.stamp_duty == 0.0005


def test_run_request_adx_defaults():
    r = BacktestRunRequest(vt_symbol="600519.SSE")
    assert r.adx_period == 14
    assert r.adx_threshold == 25.0
    assert r.trailing_stop_pct == 0.12


def test_run_request_interval_and_max_trading_days():
    r = BacktestRunRequest(vt_symbol="600519.SSE")
    assert r.interval == "d"
    assert r.max_trading_days == 20
    m = BacktestRunRequest(vt_symbol="600519.SSE", interval="1m", max_trading_days=40)
    assert m.interval == "1m"
    assert m.max_trading_days == 40


def test_optimize_request_accepts_space():
    o = OptimizeBacktestRequest(
        vt_symbol="600519.SSE",
        space={"fast_window": [5, 10], "slow_window": [20, 30]},
    )
    assert o.objective == "sharpe_ratio"
    assert o.adx_period == 14

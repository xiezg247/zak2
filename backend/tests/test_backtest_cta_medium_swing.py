from datetime import datetime, timedelta

import pytest

from app.schemas.backtest import BacktestRunRequest
from app.services.backtest.backtest_settings import build_strategy_setting, min_bars_for_request
from app.strategies.cta.registry import get_strategy_class


def test_build_setting_and_min_bars():
    req = BacktestRunRequest(
        vt_symbol="600519.SSE",
        strategy="medium_swing",
        fast_window=12,
        slow_window=26,
    )
    setting = build_strategy_setting(req)
    assert setting["fast_period"] == 12
    assert setting["slow_period"] == 26
    assert setting["signal_period"] == 9
    assert setting["trend_ma_window"] == 60
    assert min_bars_for_request(req) >= req.trend_ma_window + 5

    ma = BacktestRunRequest(vt_symbol="600519.SSE", strategy="double_ma")
    assert "signal_period" not in build_strategy_setting(ma)
    assert min_bars_for_request(ma) == 30


def test_schema_signal_fields():
    req = BacktestRunRequest(vt_symbol="600519.SSE")
    assert req.signal_period == 9
    assert req.trend_ma_window == 60


@pytest.mark.vnpy
def test_registry_medium_swing():
    pytest.importorskip("vnpy_ctastrategy")
    assert get_strategy_class("medium_swing").__name__ == "MediumSwingStrategy"


@pytest.mark.vnpy
def test_run_cta_medium_swing_synthetic():
    pytest.importorskip("vnpy_ctastrategy")
    from app.services.backtest.backtest_vnpy import run_cta_backtest

    start = datetime(2020, 1, 2)
    records = []
    price = 10.0
    for i in range(180):
        if i < 90:
            price += 0.1
        else:
            price -= 0.06
        dt = start + timedelta(days=i)
        records.append(
            {
                "datetime": dt.isoformat(),
                "open": price,
                "high": price + 0.2,
                "low": price - 0.2,
                "close": price,
                "volume": 1e6,
            }
        )

    out = run_cta_backtest(
        records,
        vt_symbol="600519.SSE",
        strategy_id="medium_swing",
        setting={
            "fast_period": 12,
            "slow_period": 26,
            "signal_period": 9,
            "trend_ma_window": 60,
            "trade_volume": 100,
        },
        start="2020-01-02",
        end="2020-12-31",
        capital=100_000,
        rate=0.00045,
        slippage=0.0,
        stamp_duty=0.0005,
    )
    assert "statistics" in out
    assert out["statistics"].get("engine") == "vnpy"

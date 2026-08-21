from __future__ import annotations

from datetime import datetime, timedelta

import pytest

pytest.importorskip("vnpy_ctastrategy")


@pytest.mark.vnpy
def test_vnpy_interval_mapping():
    from vnpy.trader.constant import Interval

    from app.domains.backtest.backtest_vnpy import vnpy_interval

    assert vnpy_interval("d") == Interval.DAILY
    assert vnpy_interval("1m") == Interval.MINUTE
    with pytest.raises(ValueError):
        vnpy_interval("5m")


@pytest.mark.vnpy
def test_run_cta_backtest_1m_synthetic():
    from app.domains.backtest.backtest_vnpy import run_cta_backtest

    start = datetime(2024, 1, 2, 9, 30)
    records = []
    price = 10.0
    for i in range(240):
        if i < 120:
            price += 0.05
        else:
            price -= 0.04
        # ~4 trading days of 1m bars (60 bars/day synthetic)
        day = i // 60
        minute = i % 60
        dt = start + timedelta(days=day, minutes=minute)
        records.append(
            {
                "datetime": dt.isoformat(),
                "open": price,
                "high": price + 0.05,
                "low": price - 0.05,
                "close": price,
                "volume": 1e5,
            }
        )

    out = run_cta_backtest(
        records,
        vt_symbol="600519.SSE",
        strategy_id="double_ma",
        setting={"fast_window": 5, "slow_window": 20, "trade_volume": 100},
        start="2024-01-02",
        end="2024-01-10",
        capital=100_000,
        rate=0.00045,
        slippage=0.0,
        stamp_duty=0.0005,
        interval="1m",
    )
    assert "total_return" in out
    assert out["statistics"].get("engine") == "vnpy"

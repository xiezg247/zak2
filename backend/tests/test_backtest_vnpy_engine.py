from __future__ import annotations

from datetime import datetime, timedelta

import pytest

pytest.importorskip("vnpy_ctastrategy")


@pytest.mark.vnpy
def test_run_cta_backtest_synthetic():
    from app.domains.backtest.backtest_vnpy import run_cta_backtest

    start = datetime(2024, 1, 2)
    records = []
    price = 10.0
    for i in range(80):
        if i < 40:
            price += 0.2
        else:
            price -= 0.15
        dt = start + timedelta(days=i)
        records.append(
            {
                "datetime": dt.isoformat(),
                "open": price,
                "high": price + 0.1,
                "low": price - 0.1,
                "close": price,
                "volume": 1e6,
            }
        )

    out = run_cta_backtest(
        records,
        vt_symbol="600519.SSE",
        strategy_id="double_ma",
        setting={"fast_window": 5, "slow_window": 20, "trade_volume": 100},
        start="2024-01-02",
        end="2024-04-30",
        capital=100_000,
        rate=0.00045,
        slippage=0.0,
        stamp_duty=0.0005,
    )
    assert "total_return" in out
    assert out.get("trade_count") is not None or out["statistics"]
    assert out["statistics"].get("engine") == "vnpy"

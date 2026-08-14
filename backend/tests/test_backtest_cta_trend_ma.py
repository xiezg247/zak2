from datetime import datetime, timedelta

import pytest
from fastapi import HTTPException

from app.schemas.backtest import BacktestRunRequest
from app.services.backtest_settings import build_strategy_setting, min_bars_for_request
from app.strategies.cta.registry import get_strategy_class

pytest.importorskip("vnpy_ctastrategy")


@pytest.mark.vnpy
def test_registry_trend_ma():
    assert get_strategy_class("trend_ma").__name__ == "TrendMaStrategy"


def test_unknown_strategy_keyerror():
    with pytest.raises(KeyError):
        get_strategy_class("no_such_strategy")


def test_build_setting_and_min_bars():
    req = BacktestRunRequest(
        vt_symbol="600519.SSE",
        strategy="trend_ma",
        fast_window=20,
        slow_window=60,
    )
    setting = build_strategy_setting(req)
    assert setting["adx_period"] == 14
    assert setting["trailing_stop_pct"] == 0.12
    assert min_bars_for_request(req) == max(30, 60 + 14 * 2 + 5)

    ma = BacktestRunRequest(vt_symbol="600519.SSE", strategy="double_ma")
    assert "adx_period" not in build_strategy_setting(ma)
    assert min_bars_for_request(ma) == 30


@pytest.mark.vnpy
def test_run_cta_trend_ma_synthetic():
    from app.services.backtest_vnpy import run_cta_backtest

    start = datetime(2020, 1, 2)
    records = []
    price = 10.0
    for i in range(120):
        if i < 70:
            price += 0.15
        else:
            price -= 0.08
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
        strategy_id="trend_ma",
        setting={
            "fast_window": 10,
            "slow_window": 30,
            "adx_period": 14,
            "adx_threshold": 10.0,
            "trailing_stop_pct": 0.12,
            "trade_volume": 100,
        },
        start="2020-01-02",
        end="2020-06-30",
        capital=100_000,
        rate=0.00045,
        slippage=0.0,
        stamp_duty=0.0005,
    )
    assert "statistics" in out
    assert out["statistics"].get("engine") == "vnpy"


def test_execute_unknown_strategy_501(monkeypatch):
    from app.services import backtest_repo as repo

    class DummyDb:
        pass

    req = BacktestRunRequest(vt_symbol="600519.SSE", strategy="ghost")
    with pytest.raises(HTTPException) as ei:
        repo.execute_single(DummyDb(), "u1", req)  # type: ignore[arg-type]
    assert ei.value.status_code == 501

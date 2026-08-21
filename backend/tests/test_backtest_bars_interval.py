from datetime import datetime, timedelta

import pytest

from app.core.errors import ValidationFailed
from app.schemas.backtest import BacktestRunRequest
from app.services.backtest.backtest_bars import Bar, count_trading_days, load_bars
from app.services.backtest.backtest_settings import min_bars_for_request


def test_count_trading_days():
    start = datetime(2024, 1, 2, 9, 30)
    bars = [Bar(dt=start + timedelta(minutes=i), open=1, high=1, low=1, close=1, volume=1) for i in range(3)]
    bars.append(Bar(dt=start + timedelta(days=1), open=1, high=1, low=1, close=1, volume=1))
    assert count_trading_days(bars) == 2


def test_max_trading_days_default():
    r = BacktestRunRequest(vt_symbol="600519.SSE")
    assert r.max_trading_days == 20
    assert r.interval == "d"


def test_min_bars_1m_floors_at_100():
    r = BacktestRunRequest(vt_symbol="600519.SSE", strategy="double_ma", interval="1m")
    assert min_bars_for_request(r) == 100
    t = BacktestRunRequest(
        vt_symbol="600519.SSE",
        strategy="trend_ma",
        interval="1m",
        fast_window=20,
        slow_window=60,
    )
    assert min_bars_for_request(t) >= 100


def test_load_bars_rejects_bad_interval():
    class DummyDb:
        pass

    with pytest.raises(ValidationFailed) as ei:
        load_bars(
            DummyDb(),  # type: ignore[arg-type]
            vt_symbol="600519.SSE",
            start_date="2024-01-01",
            end_date="2024-01-10",
            interval="5m",
        )
    assert ei.value.status_code == 400

from app.services.backtest_engine import _sma, run_double_ma, Bar
from datetime import datetime, timedelta


def test_double_ma_runs() -> None:
    start = datetime(2024, 1, 1)
    bars = []
    price = 10.0
    for i in range(80):
        # 制造一段上涨再下跌，便于产生交叉
        if i < 40:
            price += 0.15
        else:
            price -= 0.12
        bars.append(
            Bar(
                dt=start + timedelta(days=i),
                open=price,
                high=price + 0.1,
                low=price - 0.1,
                close=price,
                volume=1e6,
            )
        )
    result = run_double_ma(bars, fast_window=5, slow_window=20, capital=100_000)
    assert "total_return" in result
    assert result["bar_count"] == 80
    assert isinstance(result["equity_curve"], list)
    assert len(result["equity_curve"]) == 80


def test_sma() -> None:
    vals = [1.0, 2.0, 3.0, 4.0, 5.0]
    out = _sma(vals, 3)
    assert out[0] is None and out[1] is None
    assert abs((out[2] or 0) - 2.0) < 1e-9
    assert abs((out[4] or 0) - 4.0) < 1e-9

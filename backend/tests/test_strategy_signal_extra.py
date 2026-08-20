from __future__ import annotations

from app.services.strategy.strategy_signal_extra import (
    compute_atr_breakout_signal,
    compute_bollinger_signal,
    compute_donchian_signal,
    compute_ma_band_signal,
    compute_rsi_reversal_signal,
)


def _closes_range(start: float, step: float, count: int) -> list[float]:
    return [round(start + i * step, 4) for i in range(count)]


def test_donchian_buy_on_breakout() -> None:
    n = 30
    highs = _closes_range(10.0, 0.1, n)
    lows = _closes_range(9.9, 0.1, n)
    closes = _closes_range(9.95, 0.1, n)
    snap = compute_donchian_signal(
        highs, lows, closes, vt_symbol="1.SSE", as_of="2026-08-05"
    )
    assert snap is not None
    assert snap["signal"] == "buy"
    assert snap["signal_mode"] == "donchian"
    assert snap["channel_upper"] == 12.8


def test_donchian_insufficient_bars() -> None:
    highs = [10.0] * 10
    lows = [9.0] * 10
    closes = [9.5] * 10
    assert compute_donchian_signal(highs, lows, closes, vt_symbol="1.SSE", as_of="2026-08-05") is None


def test_rsi_reversal_buy_from_oversold() -> None:
    closes = [100.0 - i for i in range(14)] + [87.0, 89.0, 91.0, 93.0]
    snap = compute_rsi_reversal_signal(closes, vt_symbol="1.SSE", as_of="2026-08-05")
    assert snap is not None
    assert snap["signal"] == "buy"
    assert snap["signal_mode"] == "rsi_reversal"
    assert snap["rsi_value"] is not None


def test_rsi_reversal_sell_from_overbought() -> None:
    closes = [100.0 + i for i in range(14)] + [113.0, 111.0, 109.0, 107.0]
    snap = compute_rsi_reversal_signal(closes, vt_symbol="1.SSE", as_of="2026-08-05")
    assert snap is not None
    assert snap["signal"] == "sell"


def test_bollinger_buy_on_lower_band() -> None:
    closes = [10.0 + (0.05 if i % 2 else -0.05) for i in range(21)] + [10.0, 9.0]
    snap = compute_bollinger_signal(closes, vt_symbol="1.SSE", as_of="2026-08-05")
    assert snap is not None
    assert snap["signal"] == "buy"
    assert snap["signal_mode"] == "bollinger"


def test_bollinger_insufficient_bars() -> None:
    closes = [10.0] * 10
    assert compute_bollinger_signal(closes, vt_symbol="1.SSE", as_of="2026-08-05") is None


def test_ma_band_buy_on_bullish_alignment() -> None:
    closes = [10.0] * 60 + [10.0, 10.0, 10.0, 10.0, 12.5]
    snap = compute_ma_band_signal(closes, vt_symbol="1.SSE", as_of="2026-08-05")
    assert snap is not None
    assert snap["signal"] == "buy"
    assert snap["signal_mode"] == "ma_band"


def test_ma_band_sell_on_breakdown() -> None:
    closes = [10.0] * 60 + [10.5, 11.0, 11.5, 12.0, 9.0]
    snap = compute_ma_band_signal(closes, vt_symbol="1.SSE", as_of="2026-08-05")
    assert snap is not None
    assert snap["signal"] == "sell"


def test_atr_breakout_buy_on_channel_break() -> None:
    n = 32
    closes = [10.0 + (0.05 if i % 2 else -0.05) for i in range(n)]
    highs = [c + 0.1 for c in closes]
    lows = [c - 0.1 for c in closes]
    closes[-1] = 11.5
    highs[-1] = 11.6
    snap = compute_atr_breakout_signal(highs, lows, closes, vt_symbol="1.SSE", as_of="2026-08-05")
    assert snap is not None
    assert snap["signal"] == "buy"
    assert snap["signal_mode"] == "atr_breakout"
    assert snap["atr_value"] is not None


def test_atr_breakout_insufficient_bars() -> None:
    closes = [10.0] * 20
    highs = [10.1] * 20
    lows = [9.9] * 20
    assert (
        compute_atr_breakout_signal(highs, lows, closes, vt_symbol="1.SSE", as_of="2026-08-05")
        is None
    )

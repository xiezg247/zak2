from __future__ import annotations

from app.services import strategy_signal_ma as m


def test_parse_config_key() -> None:
    assert m.parse_config_key("AshareShortBreakoutStrategy:5:10") == (5, 10)
    assert m.parse_config_key("bad") is None
    assert m.parse_config_key("X:10:5") is None


def test_cross_kind() -> None:
    assert m.cross_kind(1.0, 2.0, 3.0, 2.0) == "buy"
    assert m.cross_kind(3.0, 2.0, 1.0, 2.0) == "sell"
    assert m.cross_kind(2.0, 2.0, 2.1, 2.0) == "buy"


def test_strength_tier_boundaries() -> None:
    assert m.strength_tier_for(0.29) == ("weak", "弱")
    assert m.strength_tier_for(0.3) == ("mid", "中")
    assert m.strength_tier_for(0.99) == ("mid", "中")
    assert m.strength_tier_for(1.0) == ("strong", "强")


def test_same_day_cross_is_pending_hold(monkeypatch) -> None:
    """交叉发生在 j→i（当日）→ hold 待确认。"""
    closes = [1.0] * 12

    def fake_sma(values: list[float], window: int) -> list[float | None]:
        n = len(values)
        out: list[float | None] = [None] * n
        if window == 5:
            out[-3], out[-2], out[-1] = 1.0, 1.0, 3.0
        else:
            out[-3], out[-2], out[-1] = 2.0, 2.0, 2.0
        return out

    monkeypatch.setattr(m, "sma", fake_sma)
    out = m.compute_ma_signal(
        closes, fast=5, slow=10, vt_symbol="600519.SSE", as_of="2026-08-13"
    )
    assert out is not None
    assert out["signal"] == "hold"
    assert "待确认" in out["reason_summary"]
    assert out["confirm_bars"] == 2
    assert out["strength_tier"] in {"weak", "mid", "strong"}
    assert out["strength_tier_label"] in {"弱", "中", "强"}


def test_confirmed_buy_after_cross(monkeypatch) -> None:
    """昨 k→j 金叉，今仍 fast>slow → buy 已确认。"""
    closes = [1.0] * 12

    def fake_sma(values: list[float], window: int) -> list[float | None]:
        n = len(values)
        out: list[float | None] = [None] * n
        if window == 5:
            out[-3], out[-2], out[-1] = 1.0, 3.0, 3.5
        else:
            out[-3], out[-2], out[-1] = 2.0, 2.0, 2.0
        return out

    monkeypatch.setattr(m, "sma", fake_sma)
    out = m.compute_ma_signal(
        closes, fast=5, slow=10, vt_symbol="600519.SSE", as_of="2026-08-13"
    )
    assert out is not None
    assert out["signal"] == "buy"
    assert "已确认" in out["reason_summary"]
    assert "金叉" in out["reason_summary"]
    assert out["confirm_bars"] == 2


def test_confirmed_sell_after_cross(monkeypatch) -> None:
    closes = [1.0] * 12

    def fake_sma(values: list[float], window: int) -> list[float | None]:
        n = len(values)
        out: list[float | None] = [None] * n
        if window == 5:
            out[-3], out[-2], out[-1] = 3.0, 1.0, 0.5
        else:
            out[-3], out[-2], out[-1] = 2.0, 2.0, 2.0
        return out

    monkeypatch.setattr(m, "sma", fake_sma)
    out = m.compute_ma_signal(
        closes, fast=5, slow=10, vt_symbol="600519.SSE", as_of="2026-08-13"
    )
    assert out is not None
    assert out["signal"] == "sell"
    assert "已确认" in out["reason_summary"]


def test_insufficient_slow_plus_two_returns_none() -> None:
    assert (
        m.compute_ma_signal([1.0] * 11, fast=5, slow=10, vt_symbol="x", as_of="2026-01-01")
        is None
    )


def test_double_ma_same_day_cross_is_buy(monkeypatch) -> None:
    closes = [1.0] * 12

    def fake_sma(values: list[float], window: int) -> list[float | None]:
        n = len(values)
        out: list[float | None] = [None] * n
        if window == 5:
            out[-3], out[-2], out[-1] = 1.0, 1.0, 3.0
        else:
            out[-3], out[-2], out[-1] = 2.0, 2.0, 2.0
        return out

    monkeypatch.setattr(m, "sma", fake_sma)
    d = m.compute_double_ma_signal(
        closes, fast=5, slow=10, vt_symbol="600519.SSE", as_of="2026-08-13"
    )
    h = m.compute_ma_signal(
        closes, fast=5, slow=10, vt_symbol="600519.SSE", as_of="2026-08-13"
    )
    assert d is not None and h is not None
    assert d["signal"] == "buy"
    assert d["signal_mode"] == "double_ma"
    assert "对齐回测 double_ma" in d["reason_summary"]
    assert h["signal"] == "hold"
    assert h["signal_mode"] == "heuristic_v2"


def test_trend_ma_buy_when_cross_and_adx(monkeypatch) -> None:
    n = 70
    highs = [10.0] * n
    lows = [9.0] * n
    closes = [9.5] * (n - 1) + [11.0]

    def fake_sma(values: list[float], window: int) -> list[float | None]:
        out: list[float | None] = [None] * len(values)
        if window == 20:
            out[-2], out[-1] = 9.0, 11.0
        else:
            out[-2], out[-1] = 10.0, 10.0
        return out

    monkeypatch.setattr(m, "sma", fake_sma)
    monkeypatch.setattr(m, "wilder_adx", lambda *a, **k: [None] * (n - 1) + [30.0])
    out = m.compute_trend_ma_signal(
        highs, lows, closes, fast=20, slow=60, vt_symbol="600519.SSE", as_of="2026-08-14"
    )
    assert out is not None
    assert out["signal"] == "buy"
    assert out["signal_mode"] == "trend_ma"
    assert out["adx_value"] == 30.0
    assert "不含追踪" in out["reason_summary"]


def test_trend_ma_sell_on_structure_break(monkeypatch) -> None:
    n = 70
    highs = [10.0] * n
    lows = [9.0] * n
    closes = [10.0] * (n - 1) + [9.0]

    def fake_sma(values: list[float], window: int) -> list[float | None]:
        out: list[float | None] = [None] * len(values)
        out[-2] = out[-1] = 10.0 if window == 60 else 10.5
        return out

    monkeypatch.setattr(m, "sma", fake_sma)
    monkeypatch.setattr(m, "wilder_adx", lambda *a, **k: [None] * (n - 1) + [10.0])
    out = m.compute_trend_ma_signal(
        highs, lows, closes, fast=20, slow=60, vt_symbol="600519.SSE", as_of="2026-08-14"
    )
    assert out is not None
    assert out["signal"] == "sell"

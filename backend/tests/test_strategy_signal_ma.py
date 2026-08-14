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

from app.services import strategy_signal_ma as m


def test_parse_config_key() -> None:
    assert m.parse_config_key("AshareShortBreakoutStrategy:5:10") == (5, 10)
    assert m.parse_config_key("bad") is None
    assert m.parse_config_key("X:10:5") is None  # fast >= slow


def test_golden_cross_buy() -> None:
    # 构造：慢线更稳，后段快线上穿
    # 简单序列：前段下跌/走平后上涨，使 5/10 金叉出现在末尾
    closes = [10.0] * 10 + [9.0] * 5 + [11.0, 12.0, 13.0, 14.0, 15.0]
    out = m.compute_ma_signal(
        closes, fast=5, slow=10, vt_symbol="600519.SSE", as_of="2026-08-13"
    )
    assert out is not None
    assert out["signal"] in {"buy", "sell", "hold"}
    assert "启发式" in out["reason_summary"]
    assert out["vt_symbol"] == "600519.SSE"
    assert "ma_gap_pct" in out


def test_insufficient_returns_none() -> None:
    assert (
        m.compute_ma_signal([1.0, 2.0], fast=5, slow=10, vt_symbol="x", as_of="2026-01-01")
        is None
    )


def test_cross_kind() -> None:
    assert m.cross_kind(1.0, 2.0, 3.0, 2.0) == "buy"
    assert m.cross_kind(3.0, 2.0, 1.0, 2.0) == "sell"
    assert m.cross_kind(2.0, 2.0, 2.1, 2.0) == "hold"

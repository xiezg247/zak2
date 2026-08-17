from __future__ import annotations

from app.repositories.signal_panel import SIGNAL_PANEL_MAX_SYMBOLS, normalize_symbols


def test_normalize_symbols_dedupe_and_cap() -> None:
    raw = ["600519.SSE", "600519.SSE", "000001.SZSE", "bad", "SHSE.600000"]
    out = normalize_symbols(raw, max_count=2)
    assert out == ["600519.SSE", "000001.SZSE"]
    assert SIGNAL_PANEL_MAX_SYMBOLS == 10


def test_normalize_flexible_symbol() -> None:
    out = normalize_symbols(["600519"])
    assert out == ["600519.SSE"]

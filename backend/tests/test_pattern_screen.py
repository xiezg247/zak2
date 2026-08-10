from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.schemas.screener import PatternRunRequest
from app.services import pattern_screen
from app.services.pattern_rules import BarSeries
from app.services.quotes import QuoteRow


def test_parse_tf_symbol() -> None:
    assert pattern_screen._parse_tf_symbol("SHSE.600519") == ("600519", "SSE")
    assert pattern_screen._parse_tf_symbol("SZSE.000001") == ("000001", "SZSE")


def test_run_pattern_screen_mocked() -> None:
    store = MagicMock()
    store.available.return_value = True
    store.meta.return_value = {"quote_count": 2}
    row = QuoteRow(symbol="SHSE.600519", name="茅台", change_pct=1.0, amount=1e8, total_mv=1e7)
    store.load_ranked_quotes.return_value = [row]

    closes = [10.0 + i * 0.15 for i in range(80)]
    series = BarSeries(
        closes=closes,
        highs=[c * 1.01 for c in closes],
        lows=[c * 0.99 for c in closes],
        volumes=[2000.0] * 80,
    )
    db = MagicMock()
    with (
        patch.object(pattern_screen, "_load_bar_series_batch", return_value={("600519", "SSE"): series}),
        patch.object(pattern_screen.stock_industry, "enrich_rows_from_db") as enrich,
    ):
        result = pattern_screen.run_pattern_screen(
            PatternRunRequest(pattern_id="ma_bull", top_n=10, max_scan=50),
            db=db,
            store=store,
        )
    enrich.assert_called_once()
    assert result["source"] == "bar"
    assert "均线多头" in result["condition"]
    assert result["row_count"] >= 1
    assert result["rows"][0].get("pattern_score") is not None
    assert result["rows"][0].get("pattern_hint")


def test_run_theme_hot() -> None:
    store = MagicMock()
    store.available.return_value = True
    store.meta.return_value = {"quote_count": 3}
    rows = [
        QuoteRow(symbol="SHSE.600000", name="A", change_pct=3.0, turnover_rate=5.0, amount=1e8, total_mv=1e7),
        QuoteRow(symbol="SZSE.000001", name="B", change_pct=1.0, turnover_rate=8.0, amount=1e8, total_mv=1e7),
        QuoteRow(symbol="SZSE.000002", name="C", change_pct=4.0, turnover_rate=4.0, amount=1e8, total_mv=1e7),
    ]
    store.load_ranked_quotes.return_value = rows
    db = MagicMock()
    result = pattern_screen.run_pattern_screen(
        PatternRunRequest(pattern_id="theme_hot", top_n=10, max_scan=50),
        db=db,
        store=store,
    )
    assert result["source"] == "quote"
    assert "主题" in result["condition"]
    # B 涨幅不足 2% 应剔除；A score=15, C score=16
    assert result["row_count"] == 2
    assert result["rows"][0]["name"] == "C"
    assert result["rows"][0]["pattern_score"] == 16.0

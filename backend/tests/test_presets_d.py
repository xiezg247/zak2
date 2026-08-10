from __future__ import annotations

from unittest.mock import patch

from app.schemas.screener import ConditionRunRequest, HardFilterPrefs
from app.services.engine import run_condition_screen
from app.services.presets import list_presets
from app.services.quotes import QuoteRow
from app.services import tushare_screener


def test_large_cap_and_moneyflow_presets_implemented() -> None:
    by_name = {p.name: p for p in list_presets()}
    assert by_name["中大盘"].implemented is True
    assert by_name["中大盘"].rule_kind == "large_cap"
    assert by_name["主力净流入"].implemented is True
    assert by_name["主力净流入"].rule_kind == "moneyflow_in"


def test_fetch_large_cap_filters_and_sorts() -> None:
    raw = [
        {"ts_code": "600519.SH", "close": 1800, "total_mv": 2_000_000, "circ_mv": 1_900_000, "pe_ttm": 20, "pb": 8},
        {"ts_code": "000001.SZ", "close": 10, "total_mv": 100_000, "circ_mv": 90_000, "pe_ttm": 5, "pb": 1},
        {"ts_code": "601318.SH", "close": 50, "total_mv": 800_000, "circ_mv": 700_000, "pe_ttm": 12, "pb": 2},
    ]
    with (
        patch.object(tushare_screener, "_require_token"),
        patch.object(tushare_screener, "latest_open_yyyymmdd", return_value="20240805"),
        patch.object(tushare_screener, "fetch_daily_basic_rows", return_value=raw),
    ):
        rows, trade_date, scanned = tushare_screener.fetch_large_cap_quote_rows(None)
    assert trade_date == "20240805"
    assert scanned == 3
    assert [r.symbol for r in rows] == ["SHSE.600519", "SHSE.601318"]
    assert rows[0].total_mv == 2_000_000


def test_fetch_moneyflow_in_positive_only() -> None:
    raw = [
        {"ts_code": "600519.SH", "net_mf_amount": 5000},
        {"ts_code": "000001.SZ", "net_mf_amount": -100},
        {"ts_code": "601318.SH", "net_mf_amount": 12000},
    ]
    with (
        patch.object(tushare_screener, "_require_token"),
        patch.object(tushare_screener, "latest_open_yyyymmdd", return_value="20240805"),
        patch.object(tushare_screener, "fetch_moneyflow_rows", return_value=raw),
    ):
        rows, trade_date, scanned = tushare_screener.fetch_moneyflow_in_quote_rows(None)
    assert trade_date == "20240805"
    assert scanned == 3
    assert [r.symbol for r in rows] == ["SHSE.601318", "SHSE.600519"]
    assert rows[0].net_mf_amount == 12000


def test_moneyflow_in_prefers_redis() -> None:
    class _MfStore:
        def available(self) -> bool:
            return True

        def meta(self) -> dict:
            return {"quote_count": 2, "available": True}

        def load_ranked_quotes(self, field: str, *, pool: int = 500) -> list[QuoteRow]:
            assert field == "net_mf_amount"
            return [
                QuoteRow(symbol="SHSE.A", name="流入多", net_mf_amount=9000),
                QuoteRow(symbol="SZSE.B", name="流出", net_mf_amount=-100),
                QuoteRow(symbol="SHSE.C", name="流入少", net_mf_amount=1000),
            ]

        def get_quotes(self, symbols: list[str]) -> list[QuoteRow]:
            return []

    result = run_condition_screen(
        ConditionRunRequest(
            preset="主力净流入",
            top_n=10,
            hard_filter=HardFilterPrefs(min_amount_wan=0, min_total_mv_yi=0),
        ),
        store=_MfStore(),  # type: ignore[arg-type]
    )
    assert result["source"] == "quote"
    assert result["row_count"] == 2
    assert result["rows"][0]["symbol"] == "SHSE.A"
    assert result["rows"][0]["net_mf_wan"] == 9000

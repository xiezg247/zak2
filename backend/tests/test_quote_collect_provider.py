from __future__ import annotations

import pytest

from app.services.quote_collect.provider import get_provider, parse_tickflow_row


def test_parse_change_pct_scale() -> None:
    q = parse_tickflow_row(
        {
            "symbol": "SHSE.600519",
            "name": "茅台",
            "last_price": 1800,
            "prev_close": 1780,
            "open": 1785,
            "high": 1810,
            "low": 1770,
            "volume": 1e6,
            "amount": 1e9,
            "ext.change_pct": 0.0112,
            "ext.change_amount": 20,
            "ext.turnover_rate": 0.01,
            "ext.amplitude": 0.02,
        }
    )
    assert q.symbol == "SHSE.600519"
    assert abs(q.change_pct - 1.12) < 1e-6
    assert abs(q.turnover_rate - 1.0) < 1e-6
    assert abs(q.amplitude - 2.0) < 1e-6


def test_get_provider_tickflow() -> None:
    assert get_provider("tickflow").name == "tickflow"


def test_get_provider_unknown() -> None:
    with pytest.raises(ValueError):
        get_provider("nope")


def test_fetch_batches(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.services.quote_collect import provider as p

    calls: list[list[str]] = []

    class FakeQuotes:
        def get(self, symbols, as_dataframe=True):
            calls.append(list(symbols))
            import pandas as pd

            rows = []
            for sym in symbols:
                rows.append(
                    {
                        "symbol": sym,
                        "last_price": 1.0,
                        "ext.change_pct": 0.01,
                    }
                )
            return pd.DataFrame(rows)

    class FakeClient:
        quotes = FakeQuotes()

    monkeypatch.setattr(p, "get_tickflow_client", lambda api_key="": FakeClient())
    monkeypatch.setenv("QUOTE_FETCH_MAX_WORKERS", "1")
    out = p.TickFlowProvider(api_key="x").fetch(["SHSE.600000", "SHSE.600001"])
    assert "SHSE.600000" in out
    assert "SHSE.600001" in out
    assert calls

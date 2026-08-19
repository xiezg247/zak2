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
            "trade_time": "10:31:05",
            "ext.industry": "白酒",
            "ext.total_mv": 2_100_000.0,
            "ext.circ_mv": 2_080_000.0,
            "ext.volume_ratio": 1.35,
            "ext.net_mf_amount": 123_456.0,
        }
    )
    assert q.symbol == "SHSE.600519"
    assert abs(q.change_pct - 1.12) < 1e-6
    assert abs(q.turnover_rate - 1.0) < 1e-6
    assert abs(q.amplitude - 2.0) < 1e-6
    assert q.trade_time == "10:31:05"
    assert q.industry == "白酒"
    assert abs(q.total_mv - 2_100_000.0) < 1e-6
    assert abs(q.circ_mv - 2_080_000.0) < 1e-6
    assert abs(q.volume_ratio - 1.35) < 1e-6
    assert abs(q.net_mf_amount - 123_456.0) < 1e-6


def test_get_provider_tickflow() -> None:
    assert get_provider("tickflow").name == "tickflow"


def test_get_provider_unknown() -> None:
    with pytest.raises(ValueError):
        get_provider("nope")


def test_symbol_conversion_roundtrip() -> None:
    from app.services.symbols import from_tickflow_symbol, to_tickflow_symbol

    assert to_tickflow_symbol("SHSE.600519") == "600519.SH"
    assert to_tickflow_symbol("SZSE.000001") == "000001.SZ"
    assert to_tickflow_symbol("BJSE.920000") == "920000.BJ"
    assert to_tickflow_symbol("600519") == "600519"
    assert from_tickflow_symbol("600519.SH") == "SHSE.600519"
    assert from_tickflow_symbol("920000.BJ") == "BJSE.920000"


def test_fetch_batches(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.services.quote_collect import provider as p

    calls: list[list[str]] = []

    class FakeQuotes:
        def get(self, symbols, as_dataframe=True):
            # 官方 SDK 实际返回「代码.SH/SZ/BJ」格式的 symbol 列
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

    monkeypatch.setattr(p, "get_tickflow_client", lambda **kw: FakeClient())
    monkeypatch.setenv("QUOTE_FETCH_MAX_WORKERS", "1")
    out = p.TickFlowProvider(api_key="x").fetch(["SHSE.600000", "SHSE.600001"])
    assert "SHSE.600000" in out
    assert "SHSE.600001" in out
    assert out["SHSE.600000"].symbol == "SHSE.600000"
    assert calls == [["600000.SH", "600001.SH"]]


def test_fetch_applies_batch_delay(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.services.quote_collect import provider as p

    sleeps: list[float] = []

    class FakeQuotes:
        def get(self, symbols, as_dataframe=True):
            import pandas as pd

            return pd.DataFrame(
                [{"symbol": s, "last_price": 1.0, "ext.change_pct": 0.01} for s in symbols]
            )

    class FakeClient:
        quotes = FakeQuotes()

    monkeypatch.setattr(p, "get_tickflow_client", lambda **kw: FakeClient())
    monkeypatch.setenv("QUOTE_FETCH_MAX_WORKERS", "1")
    monkeypatch.setattr(p.time, "sleep", lambda s: sleeps.append(s))
    p.TickFlowProvider(batch_delay_ms=200).fetch(["SHSE.600000", "SHSE.600001"])
    assert sleeps and all(abs(s - 0.2) < 1e-9 for s in sleeps)


def test_get_tickflow_client_passes_retries_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    import sys

    from app.integrations.tickflow import client as tc

    captured: dict[str, object] = {}

    class FakeTF:
        def __init__(self, api_key="", max_retries=None, timeout=None):
            captured["api_key"] = api_key
            captured["max_retries"] = max_retries
            captured["timeout"] = timeout

    monkeypatch.setitem(sys.modules, "tickflow", type("_t", (), {"TickFlow": FakeTF}))
    tc.get_tickflow_client(api_key="k", max_retries=5, timeout=30.0)
    assert captured == {"api_key": "k", "max_retries": 5, "timeout": 30.0}


def test_rate_limit_wait_parses_server_hint() -> None:
    from app.services.quote_collect.provider import _rate_limit_wait

    exc = type("RateLimitError", (Exception,), {})("请求频率超限 (120/min)，请 44ms 后重试")
    wait = _rate_limit_wait(exc)
    assert wait is not None
    assert wait > 0.1  # 44ms * 1.5 + 100ms 余量


def test_rate_limit_wait_ignores_other_errors() -> None:
    from app.services.quote_collect.provider import _rate_limit_wait

    assert _rate_limit_wait(ValueError("boom")) is None
    assert _rate_limit_wait(OSError("网络异常")) is None


def test_fetch_retries_on_rate_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.services.quote_collect import provider as p

    calls: list[int] = []
    sleeps: list[float] = []

    class FakeQuotes:
        def get(self, symbols, as_dataframe=True):
            calls.append(1)
            if len(calls) == 1:
                err = type("RateLimitError", (Exception,), {})("请求频率超限，请 200ms 后重试")
                raise err
            import pandas as pd

            return pd.DataFrame(
                [{"symbol": s, "last_price": 1.0, "ext.change_pct": 0.01} for s in symbols]
            )

    class FakeClient:
        quotes = FakeQuotes()

    monkeypatch.setattr(p, "get_tickflow_client", lambda **kw: FakeClient())
    monkeypatch.setattr(p.time, "sleep", lambda s: sleeps.append(s))
    out = p.TickFlowProvider().fetch(["SHSE.600000", "SHSE.600001"])
    assert "SHSE.600000" in out
    assert len(calls) == 2
    assert sleeps  # 补偿等待发生

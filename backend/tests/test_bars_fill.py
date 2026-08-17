"""bar_download / ops_bars_fill 单测（mock Tushare，不打真网）。"""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

from app.services import bar_download as bars
from app.services.ops import bars_fill as ops_bars_fill


def test_parse_universe_start_default(monkeypatch) -> None:
    monkeypatch.delenv("BARS_UNIVERSE_START", raising=False)
    assert bars.parse_universe_start(None) == date(2020, 1, 1)


def test_parse_universe_start_env(monkeypatch) -> None:
    monkeypatch.setenv("BARS_UNIVERSE_START", "2018-06-01")
    assert bars.parse_universe_start(None) == date(2018, 6, 1)


def test_parse_universe_start_invalid(monkeypatch) -> None:
    monkeypatch.setenv("BARS_UNIVERSE_START", "bad")
    assert bars.parse_universe_start(None) == date(2020, 1, 1)


def test_select_universe_daily_targets() -> None:
    uni = [("600519", "SSE"), ("000001", "SZSE"), ("300750", "SZSE")]
    starts = {
        ("600519", "SSE"): date(2020, 1, 1),  # covered
        ("000001", "SZSE"): date(2021, 1, 1),  # start too late
        # 300750 missing
    }
    out = bars.select_universe_daily_targets(
        uni, starts, unified_start=date(2020, 1, 1)
    )
    assert out == [("000001", "SZSE"), ("300750", "SZSE")]


def test_to_ts_code_and_parse() -> None:
    assert bars.to_ts_code("600519", "SSE") == "600519.SH"
    assert bars.parse_symbol_key("SHSE.600519") == ("600519", "SSE")
    assert bars.parse_symbol_key("600519.SSE") == ("600519", "SSE")


def test_is_stale_end() -> None:
    as_of = date(2024, 8, 5)
    assert bars.is_stale_end(date(2024, 8, 4), as_of=as_of) is True
    assert bars.is_stale_end(date(2024, 8, 5), as_of=as_of) is False
    assert bars.is_stale_end(None, as_of=as_of) is True


def test_resolve_fill_range_missing_and_fresh() -> None:
    db = MagicMock()
    with patch.object(bars, "get_overview_row", return_value=None):
        rng = bars.resolve_fill_range(db, symbol="600519", exchange="SSE", as_of=date(2024, 8, 5))
        assert rng is not None
        assert rng[1] == date(2024, 8, 5)

    with patch.object(
        bars,
        "get_overview_row",
        return_value={"end": date(2024, 8, 5), "start": date(2020, 1, 1), "count": 10},
    ):
        assert bars.resolve_fill_range(db, symbol="600519", exchange="SSE", as_of=date(2024, 8, 5)) is None


def test_download_daily_bars_upserts(monkeypatch) -> None:
    monkeypatch.setenv("BARS_FILL_SLEEP_SEC", "0")
    db = MagicMock()
    raw = [
        {
            "ts_code": "600519.SH",
            "trade_date": "20240805",
            "open": 10,
            "high": 11,
            "low": 9,
            "close": 10.5,
            "vol": 100,
            "amount": 1000,
        }
    ]
    with (
        patch.object(bars, "fetch_daily_rows", return_value=raw) as fetch,
        patch.object(bars, "upsert_daily_bars", return_value=1) as upsert,
    ):
        n = bars.download_daily_bars(
            db,
            symbol="600519",
            exchange="SSE",
            start=date(2024, 8, 5),
            end=date(2024, 8, 5),
        )
        assert n == 1
        fetch.assert_called_once()
        upsert.assert_called_once()


def test_fill_watchlist_no_token() -> None:
    db = MagicMock()
    with (
        patch.object(ops_bars_fill.ts, "require_token", side_effect=ops_bars_fill.ts.TushareNotConfiguredError("未配置")),
        patch.object(ops_bars_fill, "save_job_run_meta"),
    ):
        out = ops_bars_fill.fill_watchlist_bars(db)
    assert out["success"] is False
    assert "未配置" in out["message"]


def test_batch_download_universe_empty(monkeypatch) -> None:
    monkeypatch.setenv("BARS_FILL_SLEEP_SEC", "0")
    db = MagicMock()
    with (
        patch.object(ops_bars_fill.ts, "require_token"),
        patch.object(ops_bars_fill.bars, "list_universe_symbols", return_value=[]),
        patch.object(ops_bars_fill, "save_job_run_meta"),
    ):
        out = ops_bars_fill.batch_download_universe(db)
    assert out["success"] is False
    assert "列表" in out["message"] or "universe" in out["message"].lower()


def test_batch_download_universe_respects_max(monkeypatch) -> None:
    monkeypatch.setenv("BARS_FILL_MAX_SYMBOLS", "1")
    monkeypatch.setenv("BARS_FILL_SLEEP_SEC", "0")
    monkeypatch.setenv("BARS_UNIVERSE_START", "2020-01-01")
    db = MagicMock()
    with (
        patch.object(ops_bars_fill.ts, "require_token"),
        patch.object(ops_bars_fill.bars, "as_of_trade_date", return_value=date(2024, 8, 5)),
        patch.object(
            ops_bars_fill.bars,
            "list_universe_symbols",
            return_value=[("600519", "SSE"), ("000001", "SZSE")],
        ),
        patch.object(ops_bars_fill.bars, "parse_universe_start", return_value=date(2020, 1, 1)),
        patch.object(
            ops_bars_fill,
            "_load_overview_starts",
            return_value={},
        ),
        patch.object(ops_bars_fill.bars, "download_daily_bars", return_value=2) as dl,
        patch.object(ops_bars_fill, "save_job_run_meta"),
    ):
        out = ops_bars_fill.batch_download_universe(db)
    assert out["attempted"] == 1
    assert out["bars_added"] == 2
    assert dl.call_count == 1
    assert "尚余 1 只下次继续" in out["message"]


def test_batch_download_universe_prefers_missing_over_start_late(monkeypatch) -> None:
    """无 overview 标的应优先于 start 晚于统一起点的标的（max=1 时）。"""
    monkeypatch.setenv("BARS_FILL_MAX_SYMBOLS", "1")
    monkeypatch.setenv("BARS_FILL_SLEEP_SEC", "0")
    db = MagicMock()
    unified = date(2020, 1, 1)
    with (
        patch.object(ops_bars_fill.ts, "require_token"),
        patch.object(ops_bars_fill.bars, "as_of_trade_date", return_value=date(2024, 8, 5)),
        patch.object(
            ops_bars_fill.bars,
            "list_universe_symbols",
            return_value=[("600519", "SSE"), ("300750", "SZSE")],
        ),
        patch.object(ops_bars_fill.bars, "parse_universe_start", return_value=unified),
        patch.object(
            ops_bars_fill,
            "_load_overview_starts",
            return_value={("600519", "SSE"): date(2021, 1, 1)},
        ),
        patch.object(ops_bars_fill.bars, "download_daily_bars", return_value=1) as dl,
        patch.object(ops_bars_fill, "save_job_run_meta"),
    ):
        out = ops_bars_fill.batch_download_universe(db)
    assert out["attempted"] == 1
    dl.assert_called_once()
    assert dl.call_args.kwargs["symbol"] == "300750"
    assert dl.call_args.kwargs["exchange"] == "SZSE"


def test_batch_fill_stale_respects_max(monkeypatch) -> None:
    monkeypatch.setenv("BARS_FILL_MAX_SYMBOLS", "2")
    monkeypatch.setenv("BARS_FILL_SLEEP_SEC", "0")
    db = MagicMock()
    stale = [
        ("600519", "SSE", date(2024, 8, 1)),
        ("000001", "SZSE", date(2024, 8, 1)),
        ("000002", "SZSE", date(2024, 8, 1)),
    ]
    with (
        patch.object(ops_bars_fill.ts, "require_token"),
        patch.object(ops_bars_fill.bars, "as_of_trade_date", return_value=date(2024, 8, 5)),
        patch.object(ops_bars_fill.bars, "list_stale_overviews", return_value=stale[:2]) as listed,
        patch.object(ops_bars_fill, "_fill_one", return_value=("ok", 3)),
        patch.object(ops_bars_fill, "save_job_run_meta"),
    ):
        out = ops_bars_fill.batch_fill_stale(db)
    listed.assert_called_once()
    assert out["attempted"] == 2
    assert out["bars_added"] == 6
    assert out["success"] is True

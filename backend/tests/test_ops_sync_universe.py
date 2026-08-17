"""ops_sync_universe 单测（mock Tushare，不打真网）。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.services.ops import sync_universe as svc
from app.services.ops.sync_universe import parse_ts_code, rows_from_stock_basic


def test_parse_ts_code() -> None:
    assert parse_ts_code("600519.SH") == ("600519", "SSE")
    assert parse_ts_code("000001.SZ") == ("000001", "SZSE")
    assert parse_ts_code("830799.BJ") == ("830799", "BSE")
    assert parse_ts_code("600519.XX") is None
    assert parse_ts_code("") is None


def test_rows_from_stock_basic_skips_unknown() -> None:
    rows, skipped = rows_from_stock_basic(
        [
            {"ts_code": "600519.SH", "name": "茅台"},
            {"ts_code": "BAD", "name": "x"},
            {"ts_code": "000001.SZ", "name": "平安"},
        ]
    )
    assert skipped == 1
    assert rows == [
        {"symbol": "600519", "exchange": "SSE", "name": "茅台"},
        {"symbol": "000001", "exchange": "SZSE", "name": "平安"},
    ]


def test_sync_universe_empty() -> None:
    db = MagicMock()
    with (
        patch.object(svc.ts, "require_token"),
        patch.object(svc.ts, "query", return_value=[]),
        patch.object(svc, "save_job_run_meta"),
    ):
        out = svc.sync_universe(db)
    assert out.success is False
    assert "无有效标的" in out.message


def test_sync_universe_no_token() -> None:
    db = MagicMock()
    with (
        patch.object(svc.ts, "require_token", side_effect=svc.ts.TushareNotConfiguredError("未配置")),
        patch.object(svc, "save_job_run_meta"),
    ):
        out = svc.sync_universe(db)
    assert out.success is False
    assert "未配置" in out.message


def test_sync_universe_replace(monkeypatch) -> None:
    db = MagicMock()
    raw = [{"ts_code": "600519.SH", "name": "茅台"}]
    with (
        patch.object(svc.ts, "require_token"),
        patch.object(svc.ts, "query", return_value=raw) as q,
        patch.object(svc, "save_job_run_meta"),
    ):
        out = svc.sync_universe(db)
    q.assert_called_once()
    assert out.success is True
    assert out.extra["count"] == 1
    assert out.extra["skipped"] == 0
    assert db.execute.call_count >= 2
    db.commit.assert_called()

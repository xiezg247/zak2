"""limit_list_store / ops_sync_limit_list 单测（mock Tushare，不打真网）。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.services.limit_list_store import attach_first_time_fields, load_first_time_map
from app.services.ops.sync_limit_list import JOB_ID, sync_limit_list


def test_attach_first_time_fields_by_vt_and_tf() -> None:
    rows = [
        {"vt_symbol": "SHSE.600519"},
        {"tf_symbol": "SZSE.000001"},
        {"vt_symbol": "SHSE.601318"},
    ]
    first_time_map = {
        "SHSE.600519": "0935",
        "SZSE.000001": "1100",
    }
    attach_first_time_fields(rows, first_time_map)
    assert rows[0]["first_time"] == "0935"
    assert rows[0]["seal_time_score"] == 1.0
    assert rows[0]["seal_time_label"] == "09:35 封板"
    assert rows[1]["first_time"] == "1100"
    assert rows[1]["seal_time_score"] == 0.7
    assert rows[1]["seal_time_label"] == "11:00 封板"
    assert rows[2]["first_time"] == ""
    assert rows[2]["seal_time_score"] == 0.0
    assert rows[2]["seal_time_label"] == ""


def test_attach_first_time_fields_desktop_vt_resolves_tf_map() -> None:
    """情绪/雷达常见桌面键 600519.SSE，map 为 TickFlow。"""
    rows = [{"vt_symbol": "600519.SSE", "role": "最高板"}]
    attach_first_time_fields(rows, {"SHSE.600519": "0930"})
    assert rows[0]["first_time"] == "0930"
    assert rows[0]["seal_time_label"] == "09:30 封板"


def test_load_first_time_map_from_db() -> None:
    db = MagicMock()

    def _execute(stmt, params=None):
        result = MagicMock()
        if "limit_list_daily" in str(stmt):
            result.mappings.return_value = [
                {"vt_symbol": "SHSE.600519", "first_time": "0935"},
                {"vt_symbol": "SZSE.000001", "first_time": "1400"},
            ]
            return result
        return result

    db.execute.side_effect = _execute
    with patch("app.services.limit_list_store.latest_open_yyyymmdd", return_value="20240805"):
        out = load_first_time_map(db, lazy_fetch=False)
    assert out == {"SHSE.600519": "0935", "SZSE.000001": "1400"}


def test_load_first_time_map_lazy_fetch() -> None:
    db = MagicMock()
    calls = {"read": 0}

    def _execute(stmt, params=None):
        result = MagicMock()
        sql = str(stmt)
        if "SELECT vt_symbol" in sql or ("limit_list_daily" in sql and "SELECT" in sql.upper()):
            calls["read"] += 1
            if calls["read"] == 1:
                result.mappings.return_value = []
            else:
                result.mappings.return_value = [{"vt_symbol": "SHSE.600519", "first_time": "0930"}]
            return result
        return result

    db.execute.side_effect = _execute
    with (
        patch("app.services.limit_list_store.latest_open_yyyymmdd", return_value="20240805"),
        patch("app.services.limit_list_store.ts.require_token", return_value="tok"),
        patch("app.services.limit_list_store.sync_one_day", return_value=1) as sync_day,
    ):
        out = load_first_time_map(db, lazy_fetch=True)
    sync_day.assert_called_once_with(db, "20240805")
    assert out == {"SHSE.600519": "0930"}


def test_load_first_time_map_no_token_silent() -> None:
    from app.services import tushare_client as ts

    db = MagicMock()

    def _execute(stmt, params=None):
        result = MagicMock()
        result.mappings.return_value = []
        return result

    db.execute.side_effect = _execute
    with (
        patch("app.services.limit_list_store.latest_open_yyyymmdd", return_value="20240805"),
        patch(
            "app.services.limit_list_store.ts.require_token",
            side_effect=ts.TushareNotConfiguredError("未配置 TUSHARE_TOKEN"),
        ),
        patch("app.services.limit_list_store.sync_one_day") as sync_day,
    ):
        out = load_first_time_map(db, lazy_fetch=True)
    sync_day.assert_not_called()
    assert out == {}


def test_sync_limit_list_without_token() -> None:
    from app.services import tushare_client as ts

    db = MagicMock()
    with (
        patch(
            "app.services.ops.sync_limit_list.ts.require_token",
            side_effect=ts.TushareNotConfiguredError("未配置 TUSHARE_TOKEN"),
        ),
        patch("app.services.ops.sync_limit_list.save_job_run_meta") as meta,
    ):
        out = sync_limit_list(db)
    assert out["success"] is False
    assert "TUSHARE_TOKEN" in out["message"]
    assert out.get("skipped") is True
    meta.assert_called_once()
    assert meta.call_args.args[1] == JOB_ID


def test_sync_limit_list_upserts() -> None:
    db = MagicMock()
    mock_rows = [
        {
            "ts_code": "600519.SH",
            "trade_date": "20240805",
            "name": "贵州茅台",
            "limit_times": 1,
            "first_time": "0935",
            "last_time": "0935",
            "fd_amount": 1e8,
            "open_times": 0,
            "strth": 90,
        }
    ]
    with (
        patch("app.services.ops.sync_limit_list.ts.require_token", return_value="tok"),
        patch("app.services.ops.sync_limit_list.ts.query", return_value=mock_rows),
        patch("app.services.ops.sync_limit_list.recent_open_dates", return_value=["20240805"]),
        patch("app.services.ops.sync_limit_list.save_job_run_meta") as meta,
    ):
        out = sync_limit_list(db)
    assert out["success"] is True
    assert out["rows"] == 1
    assert any("INSERT INTO app.limit_list_daily" in str(c.args[0]) for c in db.execute.call_args_list)
    meta.assert_called_once()
    assert meta.call_args.kwargs["last_success"] is True

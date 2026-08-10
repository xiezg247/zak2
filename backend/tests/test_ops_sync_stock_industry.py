"""ops_sync_stock_industry 单测（mock Tushare，不打真网）。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.services import ops_sync_stock_industry as svc


def test_rows_from_sw_members() -> None:
    rows, skipped = svc.rows_from_sw_members(
        [
            {"ts_code": "600519.SH", "l1_name": "可选消费", "l2_name": "白酒", "out_date": ""},
            {"ts_code": "000001.SZ", "l1_name": "金融", "l2_name": "银行", "out_date": "20200101"},
            {"ts_code": "BAD", "l2_name": "x", "out_date": ""},
            {"ts_code": "830799.BJ", "l1_name": "综合", "l2_name": "", "out_date": ""},
        ]
    )
    assert skipped >= 2  # out_date + BAD
    assert rows[0]["symbol"] == "600519"
    assert rows[0]["industry"] == "白酒"
    assert rows[0]["industry_l1"] == "可选消费"
    assert rows[0]["source"] == "sw2021_l2"
    # BJ 无 l2 时用 l1
    assert any(r["symbol"] == "830799" and r["industry"] == "综合" for r in rows)


def test_rows_from_stock_basic_industry() -> None:
    rows, skipped = svc.rows_from_stock_basic_industry(
        [{"ts_code": "600519.SH", "industry": "白酒"}, {"ts_code": "XX", "industry": "y"}]
    )
    assert skipped == 1
    assert rows == [
        {
            "symbol": "600519",
            "exchange": "SSE",
            "industry": "白酒",
            "industry_l1": "",
            "source": "stock_basic",
        }
    ]


def test_sync_sw_success() -> None:
    db = MagicMock()
    sw = [{"ts_code": "600519.SH", "l1_name": "消费", "l2_name": "白酒", "out_date": ""}]
    with (
        patch.object(svc.ts, "require_token"),
        patch.object(svc.ts, "query", return_value=sw) as q,
        patch.object(svc, "save_job_run_meta"),
        patch.object(svc, "ensure_table"),
    ):
        out = svc.sync_stock_industry(db)
    assert out["success"] is True
    assert out["count"] == 1
    assert out["source"] == "sw2021_l2"
    q.assert_called_once()
    assert db.execute.call_count >= 2
    db.commit.assert_called()


def test_sync_fallback_stock_basic() -> None:
    db = MagicMock()
    basic = [{"ts_code": "600519.SH", "industry": "白酒"}]

    def _query(api_name, params=None, *, fields=""):
        if api_name == "index_member_all":
            return []
        return basic

    with (
        patch.object(svc.ts, "require_token"),
        patch.object(svc.ts, "query", side_effect=_query),
        patch.object(svc, "save_job_run_meta"),
        patch.object(svc, "ensure_table"),
    ):
        out = svc.sync_stock_industry(db)
    assert out["success"] is True
    assert out["source"] == "stock_basic"
    assert out["count"] == 1


def test_sync_no_token() -> None:
    db = MagicMock()
    with (
        patch.object(svc.ts, "require_token", side_effect=svc.ts.TushareNotConfiguredError("未配置")),
        patch.object(svc, "save_job_run_meta"),
    ):
        out = svc.sync_stock_industry(db)
    assert out["success"] is False
    assert "未配置" in out["message"]


def test_sync_empty_fail() -> None:
    db = MagicMock()
    with (
        patch.object(svc.ts, "require_token"),
        patch.object(svc.ts, "query", return_value=[]),
        patch.object(svc, "save_job_run_meta"),
        patch.object(svc, "ensure_table"),
    ):
        out = svc.sync_stock_industry(db)
    assert out["success"] is False
    assert "无有效" in out["message"]

from unittest.mock import MagicMock, patch

from app.services.ops import prefetch_tushare as m


def test_prefetch_skips_without_token() -> None:
    db = MagicMock()
    with patch(
        "app.services.ops.prefetch_tushare.ts.require_token",
        side_effect=m.ts.TushareNotConfiguredError("未配置 TUSHARE_TOKEN"),
    ), patch("app.services.ops.prefetch_tushare.save_job_run_meta") as save:
        out = m.prefetch_tushare(db)
    assert out["skipped"] is True
    save.assert_called_once()


def test_prefetch_upserts_basic() -> None:
    db = MagicMock()
    basic_rows = [{"ts_code": "000001.SZ", "trade_date": "20260811", "close": 10.0}]
    flow_rows = [{"ts_code": "000001.SZ", "trade_date": "20260811", "net_mf_amount": 100.0}]
    with patch("app.services.ops.prefetch_tushare.ts.require_token", return_value="tok"), patch(
        "app.services.ops.prefetch_tushare.latest_open_yyyymmdd", return_value="20260811"
    ), patch(
        "app.services.ops.prefetch_tushare.fetch_daily_basic_rows", return_value=basic_rows
    ), patch(
        "app.services.ops.prefetch_tushare.fetch_moneyflow_rows", return_value=flow_rows
    ), patch("app.services.ops.prefetch_tushare.save_job_run_meta"):
        out = m.prefetch_tushare(db)
    assert out["success"] is True
    assert out.get("written", 0) >= 1
    assert db.execute.called
    db.commit.assert_called_once()


def test_prefetch_moneyflow_failure_still_success() -> None:
    db = MagicMock()
    basic_rows = [{"ts_code": "000001.SZ", "trade_date": "20260811", "close": 10.0}]
    with patch("app.services.ops.prefetch_tushare.ts.require_token", return_value="tok"), patch(
        "app.services.ops.prefetch_tushare.latest_open_yyyymmdd", return_value="20260811"
    ), patch(
        "app.services.ops.prefetch_tushare.fetch_daily_basic_rows", return_value=basic_rows
    ), patch(
        "app.services.ops.prefetch_tushare.fetch_moneyflow_rows",
        side_effect=RuntimeError("积分不足"),
    ), patch("app.services.ops.prefetch_tushare.save_job_run_meta"):
        out = m.prefetch_tushare(db)
    assert out["success"] is True
    assert "moneyflow" in out.get("message", "").lower() or any(
        "moneyflow" in n.lower() for n in out.get("notes", [])
    )

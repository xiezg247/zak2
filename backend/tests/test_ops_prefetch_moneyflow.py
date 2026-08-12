from unittest.mock import MagicMock, patch

from app.services import ops_prefetch_moneyflow as m


def test_moneyflow_skips_without_token() -> None:
    db = MagicMock()
    with patch(
        "app.services.ops_prefetch_moneyflow.ts.require_token",
        side_effect=m.ts.TushareNotConfiguredError("未配置 TUSHARE_TOKEN"),
    ), patch("app.services.ops_prefetch_moneyflow.save_job_run_meta") as save:
        out = m.prefetch_moneyflow(db)
    assert out["skipped"] is True
    assert out["success"] is False
    save.assert_called_once()


def test_moneyflow_upserts() -> None:
    db = MagicMock()
    rows = [{"ts_code": "000001.SZ", "net_mf_amount": 1.0}]
    with patch("app.services.ops_prefetch_moneyflow.ts.require_token", return_value="tok"), patch(
        "app.services.ops_prefetch_moneyflow.latest_open_yyyymmdd", return_value="20260811"
    ), patch(
        "app.services.ops_prefetch_moneyflow.fetch_moneyflow_rows", return_value=rows
    ), patch("app.services.ops_prefetch_moneyflow.save_job_run_meta"):
        out = m.prefetch_moneyflow(db)
    assert out["success"] is True
    assert out.get("written", 0) == 1
    assert db.execute.called
    assert db.commit.called

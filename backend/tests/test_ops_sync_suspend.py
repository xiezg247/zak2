from unittest.mock import MagicMock, patch

from app.services.ops import sync_suspend as m


def test_suspend_skips_without_token() -> None:
    db = MagicMock()
    with (
        patch(
            "app.services.ops.sync_suspend.ts.require_token",
            side_effect=m.ts.TushareNotConfiguredError("未配置 TUSHARE_TOKEN"),
        ),
        patch("app.services.ops.sync_suspend.save_job_run_meta") as save,
    ):
        out = m.sync_suspend_daily(db)
    assert out.skipped is True
    save.assert_called_once()


def test_suspend_writes_rows() -> None:
    db = MagicMock()
    rows = [{"ts_code": "000001.SZ", "trade_date": "20260811", "suspend_type": "S"}]
    with (
        patch("app.services.ops.sync_suspend.ts.require_token", return_value="tok"),
        patch("app.services.ops.sync_suspend.latest_open_yyyymmdd", return_value="20260811"),
        patch("app.services.ops.sync_suspend.ts.query", return_value=rows),
        patch("app.services.ops.sync_suspend.save_job_run_meta"),
    ):
        out = m.sync_suspend_daily(db)
    assert out.success is True
    assert out.extra.get("written", 0) >= 1
    assert db.execute.called

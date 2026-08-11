from unittest.mock import MagicMock, patch

from app.services import ops_sync_disclosure as m


def test_disclosure_skips_without_token() -> None:
    db = MagicMock()
    with patch(
        "app.services.ops_sync_disclosure.ts.require_token",
        side_effect=m.ts.TushareNotConfiguredError("未配置 TUSHARE_TOKEN"),
    ), patch("app.services.ops_sync_disclosure.save_job_run_meta"):
        out = m.sync_disclosure_calendar(db)
    assert out["skipped"] is True


def test_disclosure_upserts() -> None:
    db = MagicMock()
    rows = [
        {
            "ts_code": "000001.SZ",
            "end_date": "20260630",
            "pre_date": "20260830",
            "ann_date": "",
            "actual_date": "",
        }
    ]
    with patch("app.services.ops_sync_disclosure.ts.require_token", return_value="t"), patch(
        "app.services.ops_sync_disclosure.latest_report_end_yyyymmdd", return_value="20260630"
    ), patch("app.services.ops_sync_disclosure.ts.query", return_value=rows), patch(
        "app.services.ops_sync_disclosure.save_job_run_meta"
    ):
        out = m.sync_disclosure_calendar(db)
    assert out["success"] is True
    assert out.get("written", 0) >= 1

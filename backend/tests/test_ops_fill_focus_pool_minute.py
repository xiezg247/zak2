from datetime import date
from unittest.mock import MagicMock, patch

from app.services.market import tushare_client as ts
from app.services.ops import fill_focus_pool_minute as m


def test_minute_skips_without_token() -> None:
    db = MagicMock()
    with (
        patch.object(m.ts, "require_token", side_effect=ts.TushareNotConfiguredError("未配置")),
        patch("app.services.ops.fill_focus_pool_minute.save_job_run_meta") as save,
    ):
        out = m.fill_focus_pool_minute(db)
    assert out.skipped is True
    assert out.success is False
    assert "未接入" not in out.message
    assert save.call_args.kwargs["last_success"] is False


def test_minute_downloads() -> None:
    db = MagicMock()
    pool = [("600519", "SSE")]
    with (
        patch.object(m.ts, "require_token", return_value="t"),
        patch.object(m, "list_watchlist_symbols", return_value=pool),
        patch.object(m, "_lookback_days", return_value=5),
        patch.object(m, "_max_symbols", return_value=50),
        patch.object(m, "_open_date_window", return_value=(date(2026, 8, 7), date(2026, 8, 13))),
        patch.object(m, "_needs_1m_download", return_value=True),
        patch.object(m, "download_minute_bars", return_value=100) as dl,
        patch.object(m, "_count_overview", side_effect=[1, 1]),
        patch.object(m, "_sleep", return_value=None),
        patch("app.services.ops.fill_focus_pool_minute.save_job_run_meta") as save,
    ):
        out = m.fill_focus_pool_minute(db)
    assert out.success is True
    assert out.skipped is False
    assert out.extra["downloaded"] == 1
    assert out.extra["bars_added"] == 100
    assert "未接入" not in out.message
    dl.assert_called_once()
    assert save.call_args.kwargs["last_success"] is True


def test_minute_empty_pool_ok() -> None:
    db = MagicMock()
    with (
        patch.object(m.ts, "require_token", return_value="t"),
        patch.object(m, "list_watchlist_symbols", return_value=[]),
        patch.object(m, "_lookback_days", return_value=5),
        patch.object(m, "_max_symbols", return_value=50),
        patch("app.services.ops.fill_focus_pool_minute.save_job_run_meta"),
    ):
        out = m.fill_focus_pool_minute(db)
    assert out.success is True
    assert out.extra["pool_size"] == 0
    assert out.extra["downloaded"] == 0
    assert "未接入" not in out.message

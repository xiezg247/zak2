from unittest.mock import MagicMock, patch

from app.services import ops_fill_focus_pool_minute as m


def test_minute_inventory_success() -> None:
    db = MagicMock()
    pool = [("600519", "SSE"), ("000001", "SZSE")]
    with (
        patch.object(m, "list_watchlist_symbols", return_value=pool),
        patch.object(m, "_count_overview", side_effect=[2, 0]),  # daily, 1m
        patch("app.services.ops_fill_focus_pool_minute.save_job_run_meta") as save,
    ):
        out = m.fill_focus_pool_minute(db)
    assert out["skipped"] is False
    assert out["success"] is True
    assert out["pool_size"] == 2
    assert out["with_daily"] == 2
    assert out["with_1m"] == 0
    assert out["missing_1m"] == 2
    assert "1m 下载未接入" in out["message"]
    assert "盘点" in out["message"]
    save.assert_called_once()
    assert save.call_args.kwargs["last_success"] is True


def test_minute_empty_pool_still_success() -> None:
    db = MagicMock()
    with (
        patch.object(m, "list_watchlist_symbols", return_value=[]),
        patch("app.services.ops_fill_focus_pool_minute.save_job_run_meta") as save,
    ):
        out = m.fill_focus_pool_minute(db)
    assert out["success"] is True
    assert out["skipped"] is False
    assert out["pool_size"] == 0
    assert out["missing_1m"] == 0
    assert "1m 下载未接入" in out["message"]
    assert save.call_args.kwargs["last_success"] is True

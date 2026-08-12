from unittest.mock import MagicMock, patch

from app.services import ops_fill_focus_pool_minute as m


def test_minute_skips() -> None:
    db = MagicMock()
    with patch("app.services.ops_fill_focus_pool_minute.save_job_run_meta") as save:
        out = m.fill_focus_pool_minute(db)
    assert out["skipped"] is True
    assert out["success"] is False
    assert "1m" in out["message"] or "分钟" in out["message"]
    save.assert_called_once()
    assert save.call_args.kwargs["last_success"] is False

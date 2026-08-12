from unittest.mock import MagicMock, patch

from app.services import ops_scan_horizon_outlook as m


def test_horizon_skips() -> None:
    db = MagicMock()
    with patch("app.services.ops_scan_horizon_outlook.save_job_run_meta") as save:
        out = m.scan_horizon_outlook(db)
    assert out["skipped"] is True
    assert out["success"] is False
    assert "展望" in out["message"] or "扫描" in out["message"]
    save.assert_called_once()
    assert save.call_args.kwargs["last_success"] is False

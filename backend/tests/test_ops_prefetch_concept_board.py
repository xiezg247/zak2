from unittest.mock import MagicMock, patch

from app.schemas.ops import SyncResult
from app.services.ops import prefetch_concept_board as m


def test_concept_delegates_success() -> None:
    db = MagicMock()
    child = SyncResult(success=True, skipped=False, message="ok 2 days", extra={"days": 2})
    with (
        patch("app.services.ops.prefetch_concept_board.sync_sector_flow_daily", return_value=child),
        patch("app.services.ops.prefetch_concept_board.save_job_run_meta") as save,
    ):
        out = m.prefetch_concept_board(db)
    assert out.skipped is False
    assert out.success is True
    assert "概念预拉" in out.message
    assert "sector sync" in out.message or "ok" in out.message
    save.assert_called_once()
    assert save.call_args.kwargs["last_success"] is True


def test_concept_delegates_skipped() -> None:
    db = MagicMock()
    child = SyncResult(success=False, skipped=True, message="Tushare token missing", extra={"days": 0})
    with (
        patch("app.services.ops.prefetch_concept_board.sync_sector_flow_daily", return_value=child),
        patch("app.services.ops.prefetch_concept_board.save_job_run_meta") as save,
    ):
        out = m.prefetch_concept_board(db)
    assert out.skipped is True
    assert out.success is False
    assert "token" in out.message.lower() or "Tushare" in out.message
    assert save.call_args.kwargs["last_success"] is False

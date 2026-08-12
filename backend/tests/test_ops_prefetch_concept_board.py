from unittest.mock import MagicMock, patch

from app.services import ops_prefetch_concept_board as m


def test_concept_skips() -> None:
    db = MagicMock()
    with patch("app.services.ops_prefetch_concept_board.save_job_run_meta") as save:
        out = m.prefetch_concept_board(db)
    assert out["skipped"] is True
    assert out["success"] is False
    assert "概念" in out["message"]
    save.assert_called_once()
    assert save.call_args.kwargs["last_success"] is False

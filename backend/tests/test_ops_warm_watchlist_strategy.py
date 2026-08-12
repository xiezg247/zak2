from unittest.mock import MagicMock, patch

from app.services import ops_warm_watchlist_strategy as m


def test_warm_strategy_skips() -> None:
    db = MagicMock()
    with patch("app.services.ops_warm_watchlist_strategy.save_job_run_meta") as save:
        out = m.warm_watchlist_strategy_cache(db)
    assert out["skipped"] is True
    assert out["success"] is False
    assert "策略引擎" in out["message"]
    save.assert_called_once()
    assert save.call_args.kwargs["last_success"] is False

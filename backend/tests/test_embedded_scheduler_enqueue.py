from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.services import embedded_scheduler as es


def test_run_job_enqueues_instead_of_local_runner() -> None:
    settings = MagicMock()
    settings.scheduler_effective_enabled = True
    settings.scheduler_screen_user_id = ""

    # Ensure process lock is free
    lock = es._locks["sync_universe"]
    if lock.locked():
        lock.release()

    with (
        patch.object(es, "get_settings", return_value=settings),
        patch.object(es.scheduler_lock, "try_acquire", return_value=True),
        patch.object(es.scheduler_lock, "release"),
        patch.object(es.scheduler_lock, "make_token", return_value="t"),
        patch.object(es, "SessionLocal") as SL,
        patch.object(
            es,
            "load_scheduler_config",
            return_value={"config": {"sync_universe": {"enabled": True}}},
        ),
        patch.object(es, "enqueue_ops_job_sync", return_value="jid") as enq,
        patch.object(es, "needs_user_id", return_value=False),
    ):
        SL.return_value = MagicMock()
        with es._running_guard:
            es._running.discard("sync_universe")
            es._running -= es._BARS_JOBS
        es._run_job("sync_universe")

    enq.assert_called_once_with("sync_universe", user_id=None, force=False)

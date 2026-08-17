from unittest.mock import MagicMock, patch

import pytest

from app.services import embedded_scheduler as es
from app.services.ops.catalog import RUNNABLE_JOB_IDS


@pytest.fixture(autouse=True)
def _default_scheduler_lock(monkeypatch) -> None:
    monkeypatch.setattr(es.scheduler_lock, "make_token", lambda: "test-token")
    monkeypatch.setattr(es.scheduler_lock, "try_acquire", lambda *args, **kwargs: True)
    monkeypatch.setattr(es.scheduler_lock, "release", lambda *args, **kwargs: None)


def test_runners_cover_runnable() -> None:
    from app.services.ops.runners import RUNNERS

    assert set(RUNNERS) == set(RUNNABLE_JOB_IDS)


def test_run_job_skips_when_master_disabled(monkeypatch) -> None:
    monkeypatch.setattr(
        es,
        "get_settings",
        lambda: type("S", (), {"scheduler_effective_enabled": False, "scheduler_screen_user_id": ""})(),
    )
    with patch.object(es, "SessionLocal") as sl:
        es._run_job("purge_stale_cache")
    sl.assert_not_called()


def test_run_job_skips_when_not_enabled(monkeypatch) -> None:
    monkeypatch.setattr(
        es,
        "get_settings",
        lambda: type("S", (), {"scheduler_effective_enabled": True, "scheduler_screen_user_id": "u1"})(),
    )
    db = MagicMock()
    monkeypatch.setattr(es, "SessionLocal", lambda: db)
    monkeypatch.setattr(
        es,
        "load_scheduler_config",
        lambda _db: {"config": {"purge_stale_cache": {"enabled": False}}},
    )
    enq = MagicMock()
    monkeypatch.setattr(es, "enqueue_ops_job_sync", enq)
    es._run_job("purge_stale_cache")
    enq.assert_not_called()


def test_screen_skips_without_user(monkeypatch) -> None:
    monkeypatch.setattr(
        es,
        "get_settings",
        lambda: type("S", (), {"scheduler_effective_enabled": True, "scheduler_screen_user_id": ""})(),
    )
    db = MagicMock()
    monkeypatch.setattr(es, "SessionLocal", lambda: db)
    monkeypatch.setattr(
        es,
        "load_scheduler_config",
        lambda _db: {"config": {"screen_intraday": {"enabled": True}}},
    )
    enq = MagicMock()
    monkeypatch.setattr(es, "enqueue_ops_job_sync", enq)
    es._run_job("screen_intraday")
    enq.assert_not_called()


def test_screen_calls_with_user(monkeypatch) -> None:
    monkeypatch.setattr(
        es,
        "get_settings",
        lambda: type(
            "S",
            (),
            {"scheduler_effective_enabled": True, "scheduler_screen_user_id": "user-1"},
        )(),
    )
    db = MagicMock()
    monkeypatch.setattr(es, "SessionLocal", lambda: db)
    monkeypatch.setattr(
        es,
        "load_scheduler_config",
        lambda _db: {"config": {"screen_intraday": {"enabled": True}}},
    )
    enq = MagicMock(return_value="jid")
    monkeypatch.setattr(es, "enqueue_ops_job_sync", enq)
    es._run_job("screen_intraday")
    enq.assert_called_once_with("screen_intraday", user_id="user-1", force=False)


def test_watchlist_skips_when_stale_running(monkeypatch) -> None:
    monkeypatch.setattr(
        es,
        "get_settings",
        lambda: type("S", (), {"scheduler_effective_enabled": True, "scheduler_screen_user_id": ""})(),
    )
    with es._running_guard:
        es._running.add("batch_fill_stale")
    try:
        with patch.object(es, "SessionLocal") as sl:
            es._run_job("fill_watchlist_bars")
        sl.assert_not_called()
    finally:
        with es._running_guard:
            es._running.discard("batch_fill_stale")


def test_universe_skips_when_stale_running(monkeypatch) -> None:
    monkeypatch.setattr(
        es,
        "get_settings",
        lambda: type("S", (), {"scheduler_effective_enabled": True, "scheduler_screen_user_id": ""})(),
    )
    with es._running_guard:
        es._running.add("batch_fill_stale")
    try:
        with patch.object(es, "SessionLocal") as sl:
            es._run_job("batch_download_universe")
        sl.assert_not_called()
    finally:
        with es._running_guard:
            es._running.discard("batch_fill_stale")


def test_watchlist_skips_when_universe_running(monkeypatch) -> None:
    monkeypatch.setattr(
        es,
        "get_settings",
        lambda: type("S", (), {"scheduler_effective_enabled": True, "scheduler_screen_user_id": ""})(),
    )
    with es._running_guard:
        es._running.add("batch_download_universe")
    try:
        with patch.object(es, "SessionLocal") as sl:
            es._run_job("fill_watchlist_bars")
        sl.assert_not_called()
    finally:
        with es._running_guard:
            es._running.discard("batch_download_universe")


def test_run_job_skips_when_distributed_lock_not_acquired(monkeypatch) -> None:
    monkeypatch.setattr(
        es,
        "get_settings",
        lambda: type("S", (), {"scheduler_effective_enabled": True, "scheduler_screen_user_id": ""})(),
    )
    monkeypatch.setattr(es.scheduler_lock, "try_acquire", lambda *args, **kwargs: False)
    release = MagicMock()
    monkeypatch.setattr(es.scheduler_lock, "release", release)
    db = MagicMock()
    monkeypatch.setattr(es, "SessionLocal", lambda: db)
    monkeypatch.setattr(
        es,
        "load_scheduler_config",
        lambda _db: {"config": {"purge_stale_cache": {"enabled": True}}},
    )
    enq = MagicMock()
    monkeypatch.setattr(es, "enqueue_ops_job_sync", enq)
    es._run_job("purge_stale_cache")
    enq.assert_not_called()
    release.assert_not_called()
    assert "purge_stale_cache" not in es._running


def test_run_job_releases_distributed_lock_in_finally(monkeypatch) -> None:
    monkeypatch.setattr(
        es,
        "get_settings",
        lambda: type("S", (), {"scheduler_effective_enabled": True, "scheduler_screen_user_id": ""})(),
    )
    release = MagicMock()
    monkeypatch.setattr(es.scheduler_lock, "release", release)
    db = MagicMock()
    monkeypatch.setattr(es, "SessionLocal", lambda: db)
    monkeypatch.setattr(
        es,
        "load_scheduler_config",
        lambda _db: {"config": {"purge_stale_cache": {"enabled": True}}},
    )
    enq = MagicMock(return_value="jid")
    monkeypatch.setattr(es, "enqueue_ops_job_sync", enq)
    es._run_job("purge_stale_cache")
    enq.assert_called_once_with("purge_stale_cache", user_id=None, force=False)
    release.assert_called_once_with("purge_stale_cache", "test-token")

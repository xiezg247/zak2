# backend/tests/test_ops_arq_worker.py
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.worker import tasks as t


@pytest.mark.asyncio
async def test_run_ops_job_unknown_raises() -> None:
    with pytest.raises(ValueError, match="未知"):
        await t.run_ops_job({}, "not_a_real_job")


@pytest.mark.asyncio
async def test_run_ops_job_calls_runner_in_thread() -> None:
    db = MagicMock()
    runner = MagicMock(return_value={"success": True, "message": "done"})
    with (
        patch("app.worker.tasks.SessionLocal", return_value=db),
        patch.dict("app.worker.tasks.RUNNERS", {"sync_universe": runner}, clear=False),
        patch("app.worker.tasks.needs_user_id", return_value=False),
    ):
        out = await t.run_ops_job({}, "sync_universe", user_id=None, force=False)
    assert out["success"] is True
    runner.assert_called_once_with(db)
    db.close.assert_called_once()


@pytest.mark.asyncio
async def test_run_ops_job_bilibili_respects_force() -> None:
    db = MagicMock()
    with (
        patch("app.worker.tasks.SessionLocal", return_value=db),
        patch("app.worker.tasks.ops_sync_bilibili_feed.sync_bilibili_feed") as sync_fn,
        patch("app.worker.tasks.ops_sync_bilibili_feed.JOB_ID", "sync_bilibili_feed"),
    ):
        sync_fn.return_value = {"success": True, "message": "feed"}
        await t.run_ops_job({}, "sync_bilibili_feed", force=False)
    sync_fn.assert_called_once_with(db, force=False)

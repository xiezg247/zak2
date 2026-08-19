from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import MagicMock, patch

from app.services.ops import arq_jobs


async def _ok(value: Any) -> Any:
    """返回一个 await 结果为 value 的协程。"""
    return value


def test_auto_arq_id() -> None:
    assert arq_jobs.auto_arq_id("7") == "auto:7"


def test_enqueue_auto_task_uses_stable_id() -> None:
    pool = MagicMock()
    pool.delete.side_effect = lambda *_: _ok(None)
    pool.zrem.return_value = _ok(None)
    job = MagicMock()
    job.job_id = "auto:7"
    pool.enqueue_job.return_value = _ok(job)

    async def _go() -> str:
        with (
            patch.object(arq_jobs, "_arq_pool", return_value=pool),
            patch("app.core.settings.get_settings") as gs,
        ):
            gs.return_value.arq_queue_name = "zak2:arq"
            probe = MagicMock()
            probe.status.return_value = _ok("not_found")
            with patch("app.services.ops.arq_jobs.Job", return_value=probe):
                return await arq_jobs.enqueue_auto_task("7")

    arq_id = asyncio.run(_go())
    assert arq_id == "auto:7"
    assert pool.enqueue_job.call_args.args[0] == "run_auto_schedule_task"
    assert pool.enqueue_job.call_args.args[1] == "7"
    assert pool.enqueue_job.call_args.kwargs["_job_id"] == "auto:7"


def test_enqueue_auto_task_reuses_inflight() -> None:
    pool = MagicMock()

    async def _go() -> str:
        with (
            patch.object(arq_jobs, "_arq_pool", return_value=pool),
            patch("app.core.settings.get_settings") as gs,
        ):
            gs.return_value.arq_queue_name = "zak2:arq"
            probe = MagicMock()
            probe.status.return_value = _ok("in_progress")
            with patch("app.services.ops.arq_jobs.Job", return_value=probe):
                return await arq_jobs.enqueue_auto_task("7")

    arq_id = asyncio.run(_go())
    assert arq_id == "auto:7"
    pool.enqueue_job.assert_not_called()

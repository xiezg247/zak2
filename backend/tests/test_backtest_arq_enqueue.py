import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services import arq_jobs


@pytest.mark.asyncio
async def test_enqueue_backtest_uses_backtest_queue():
    mock_job = MagicMock()
    mock_job.job_id = "job-bt-1"
    mock_pool = MagicMock()
    mock_pool.enqueue_job = AsyncMock(return_value=mock_job)

    with (
        patch.object(arq_jobs, "_arq_pool", AsyncMock(return_value=mock_pool)),
        patch.object(arq_jobs, "_sync_redis", return_value=MagicMock()),
        patch.object(arq_jobs, "index_job"),
    ):
        job_id = await arq_jobs.enqueue_app_job(
            function="run_backtest_single",
            kind="backtest.single",
            user_id="u1",
            payload={"vt_symbol": "600519.SSE"},
        )
    assert job_id == "job-bt-1"
    kwargs = mock_pool.enqueue_job.await_args.kwargs
    assert kwargs["_queue_name"] == "zak2:arq:backtest"

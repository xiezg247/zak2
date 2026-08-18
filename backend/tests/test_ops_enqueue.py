from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from arq.jobs import JobStatus

from app.schemas.screener import JobOut
from app.services.ops import arq_jobs as m


def test_index_job_writes_unified_zset() -> None:
    client = MagicMock()
    m.index_job(
        client,
        arq_id="ops:sync_universe",
        kind="ops.sync_universe",
        user_id="u1",
        created_at="2026-08-14T03:00:00+00:00",
        score_ms=1_723_600_000_000,
        ops_job_id="sync_universe",
    )
    client.zadd.assert_called_once()
    client.hset.assert_called_once()
    client.zremrangebyrank.assert_called_once()


@pytest.mark.asyncio
async def test_enqueue_ops_returns_existing_when_in_progress() -> None:
    fake_pool = AsyncMock()
    fake_pool.enqueue_job = AsyncMock()
    with (
        patch.object(m, "_arq_pool", AsyncMock(return_value=fake_pool)),
        patch("app.services.ops.arq_jobs.Job") as JobCls,
    ):
        inst = AsyncMock()
        inst.status = AsyncMock(return_value=JobStatus.in_progress)
        JobCls.return_value = inst
        with patch.object(m, "_sync_redis", return_value=MagicMock()), patch.object(m, "index_job"):
            out = await m.enqueue_ops_job("sync_universe", user_id="u1")
    assert out == "ops:sync_universe"
    fake_pool.enqueue_job.assert_not_called()


@pytest.mark.asyncio
async def test_enqueue_ops_clears_complete_then_enqueues() -> None:
    fake_job = MagicMock()
    fake_job.job_id = "ops:sync_universe"
    fake_pool = AsyncMock()
    fake_pool.enqueue_job = AsyncMock(return_value=fake_job)
    fake_pool.delete = AsyncMock()
    fake_pool.zrem = AsyncMock()

    with (
        patch.object(m, "_arq_pool", AsyncMock(return_value=fake_pool)),
        patch("app.services.ops.arq_jobs.Job") as JobCls,
        patch.object(m, "_sync_redis", return_value=MagicMock()),
        patch.object(m, "index_job") as idx,
    ):
        inst = AsyncMock()
        inst.status = AsyncMock(return_value=JobStatus.complete)
        JobCls.return_value = inst
        out = await m.enqueue_ops_job("sync_universe", user_id="u1", force=True)

    assert out == "ops:sync_universe"
    fake_pool.delete.assert_awaited()
    fake_pool.enqueue_job.assert_awaited_once()
    assert fake_pool.enqueue_job.await_args.kwargs.get("_job_id") == "ops:sync_universe"
    idx.assert_called_once()


@pytest.mark.asyncio
async def test_map_complete_success_to_job_out() -> None:
    info = MagicMock()
    info.success = True
    info.result = {"success": True, "message": "ok"}
    info.enqueue_time = datetime(2026, 8, 14, 3, 0, 0, tzinfo=UTC)
    info.finish_time = datetime(2026, 8, 14, 3, 1, 0, tzinfo=UTC)

    out = m._job_out_from_arq(
        job_id="ops:sync_universe",
        kind="ops.sync_universe",
        status_name="complete",
        result_info=info,
        created_at_fallback="2026-08-14T03:00:00+00:00",
    )
    assert isinstance(out, JobOut)
    assert out.status == "success"
    assert out.result_ref == "ok"

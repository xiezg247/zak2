# backend/tests/test_ops_enqueue.py
from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.schemas.screener import JobOut
from app.services import ops_enqueue as m


def test_index_ops_job_writes_zset_and_hash() -> None:
    client = MagicMock()
    m._index_ops_job(
        client,
        arq_id="abc123",
        ops_job_id="sync_universe",
        user_id="u1",
        created_at="2026-08-14T03:00:00+00:00",
        score_ms=1_723_600_000_000,
    )
    client.zadd.assert_called_once()
    client.hset.assert_called_once()
    client.zremrangebyrank.assert_called_once()


@pytest.mark.asyncio
async def test_enqueue_ops_job_returns_arq_id_and_indexes() -> None:
    fake_job = MagicMock()
    fake_job.job_id = "jid-1"
    fake_pool = AsyncMock()
    fake_pool.enqueue_job = AsyncMock(return_value=fake_job)
    redis_sync = MagicMock()

    with (
        patch.object(m, "_arq_pool", AsyncMock(return_value=fake_pool)),
        patch.object(m, "_sync_redis", return_value=redis_sync),
        patch.object(m, "_index_ops_job") as idx,
    ):
        out = await m.enqueue_ops_job("sync_universe", user_id="u1", force=False)

    assert out == "jid-1"
    fake_pool.enqueue_job.assert_awaited_once()
    assert fake_pool.enqueue_job.await_args.args[0] == "run_ops_job"
    idx.assert_called_once()


@pytest.mark.asyncio
async def test_map_complete_success_to_job_out() -> None:
    info = MagicMock()
    info.success = True
    info.result = {"success": True, "message": "ok"}
    info.enqueue_time = datetime(2026, 8, 14, 3, 0, 0, tzinfo=UTC)
    info.finish_time = datetime(2026, 8, 14, 3, 1, 0, tzinfo=UTC)

    out = m._job_out_from_arq(
        job_id="jid-1",
        ops_job_id="sync_universe",
        status_name="complete",
        result_info=info,
        created_at_fallback="2026-08-14T03:00:00+00:00",
    )
    assert isinstance(out, JobOut)
    assert out.id == "jid-1"
    assert out.kind == "ops.sync_universe"
    assert out.status == "success"
    assert out.result_ref == "ok"

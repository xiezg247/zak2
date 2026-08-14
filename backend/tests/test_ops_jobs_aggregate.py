from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.api.v1 import jobs as jobs_api
from app.jobs.store import job_store
from app.schemas.screener import JobOut


@pytest.mark.asyncio
async def test_resolve_prefers_memory() -> None:
    mem = job_store.create("backtest.x")
    with patch.object(jobs_api, "get_ops_job_out", new_callable=AsyncMock) as g:
        out = await jobs_api._resolve_job(mem.id)
    assert out is not None
    assert out.id == mem.id
    assert out.kind == "backtest.x"
    g.assert_not_called()


@pytest.mark.asyncio
async def test_resolve_falls_back_to_arq() -> None:
    arq_out = JobOut(
        id="arq-1",
        kind="ops.sync_universe",
        status="success",
        progress=1.0,
        error=None,
        result_ref="ok",
        created_at="2026-08-14T03:00:00+00:00",
        updated_at="2026-08-14T03:01:00+00:00",
    )
    with patch.object(jobs_api, "get_ops_job_out", new_callable=AsyncMock, return_value=arq_out) as g:
        out = await jobs_api._resolve_job("arq-1")
    assert out == arq_out
    g.assert_awaited_once_with("arq-1")


@pytest.mark.asyncio
async def test_list_merges_memory_and_ops() -> None:
    mem = job_store.create("screener.y")
    ops_row = JobOut(
        id="arq-2",
        kind="ops.sync_universe",
        status="pending",
        progress=0.0,
        created_at="2099-01-01T00:00:00+00:00",
        updated_at="2099-01-01T00:00:00+00:00",
    )
    with patch.object(jobs_api, "list_ops_job_outs", new_callable=AsyncMock, return_value=[ops_row]):
        rows = await jobs_api._list_merged(limit=50)
    ids = {r.id for r in rows}
    assert mem.id in ids
    assert "arq-2" in ids
    assert rows[0].id == "arq-2"

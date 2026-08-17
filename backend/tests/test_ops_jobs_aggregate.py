from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.api.v1 import jobs as jobs_api
from app.schemas.screener import JobOut


@pytest.mark.asyncio
async def test_list_jobs_delegates() -> None:
    rows = [
        JobOut(
            id="a",
            kind="ops.sync_universe",
            status="pending",
            created_at="2026-08-14T00:00:00+00:00",
            updated_at="2026-08-14T00:00:00+00:00",
        )
    ]
    with patch.object(jobs_api, "list_job_outs", new_callable=AsyncMock, return_value=rows):
        out = await jobs_api.list_jobs(user=MagicMock())  # type: ignore[arg-type]
    assert out.data == rows


from unittest.mock import MagicMock  # noqa: E402


@pytest.mark.asyncio
async def test_get_job_404() -> None:
    from fastapi import HTTPException

    with patch.object(jobs_api, "get_job_out", new_callable=AsyncMock, return_value=None), pytest.raises(HTTPException) as ei:
        await jobs_api.get_job("missing", user=MagicMock())  # type: ignore[arg-type]
    assert ei.value.status_code == 404

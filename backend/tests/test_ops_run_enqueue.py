from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.core.db import get_db
from app.core.security import hash_password
from app.main import create_app
from app.models.user import User


def _make_user() -> User:
    now = datetime.now(UTC)
    return User(
        id=str(uuid4()),
        username="demo",
        display_name="Demo",
        password_hash=hash_password("demo-pass"),
        is_active=True,
        created_at=now,
        updated_at=now,
    )


def _api_client(user: User | None = None) -> TestClient:
    app = create_app()
    u = user or _make_user()

    def override_db():  # type: ignore[no-untyped-def]
        yield MagicMock()

    def override_user():  # type: ignore[no-untyped-def]
        return u

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user
    return TestClient(app)


def test_run_scheduler_job_enqueues() -> None:
    client = _api_client()
    with (
        patch("app.api.v1.ops.ops_scheduler.job_kind_for", return_value="runnable"),
        patch(
            "app.api.v1.ops.enqueue_ops_job",
            new_callable=AsyncMock,
            return_value="arq-id-1",
        ) as enq,
    ):
        r = client.post("/api/v1/ops/scheduler/jobs/sync_universe/run")
    assert r.status_code == 200
    body = r.json()
    assert body["job_id"] == "arq-id-1"
    assert body["kind"] == "ops.sync_universe"
    enq.assert_awaited_once()
    assert enq.await_args.args[0] == "sync_universe"
    assert enq.await_args.kwargs.get("force") is True

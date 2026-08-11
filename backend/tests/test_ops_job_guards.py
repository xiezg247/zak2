from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch
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


def test_patch_planned_job_returns_400() -> None:
    client = _api_client()
    with patch("app.services.ops_scheduler.patch_job_enabled") as p:
        r = client.patch("/api/v1/ops/scheduler/jobs/enrich_market_quotes", json={"enabled": True})
    assert r.status_code == 400
    p.assert_not_called()


def test_run_process_job_returns_400() -> None:
    client = _api_client()
    r = client.post("/api/v1/ops/scheduler/jobs/collect_quotes/run")
    assert r.status_code == 400

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
from app.schemas.ops import SchedulerJobOut


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


def _planned_job_row(*, enabled: bool = False) -> SchedulerJobOut:
    return SchedulerJobOut(
        job_id="purge_stale_cache",
        name="清理过期缓存",
        description="删除 cache schema 中过期 LLM/雷达 hint 与过旧策略缓存",
        job_kind="planned",
        runnable=False,
        run_hint="未实现：见 docs/product-roadmap.md",
        status_label="未实现",
        enabled=enabled,
        cron_hour=None,
        cron_minute=None,
        cron_day_of_week=None,
        interval_seconds=None,
        last_run=None,
    )


def test_patch_planned_job_enabled_true_returns_400() -> None:
    client = _api_client()
    with (
        patch("app.api.v1.ops.ops_scheduler.job_kind_for", return_value="planned"),
        patch("app.services.ops.scheduler.patch_job_enabled") as p,
    ):
        r = client.patch("/api/v1/ops/scheduler/jobs/purge_stale_cache", json={"enabled": True})
    assert r.status_code == 400
    p.assert_not_called()


def test_patch_planned_job_enabled_false_returns_200() -> None:
    client = _api_client()
    with (
        patch("app.api.v1.ops.ops_scheduler.job_kind_for", return_value="planned"),
        patch("app.services.ops.scheduler.patch_job_enabled") as p,
        patch("app.services.ops.scheduler.list_scheduler_jobs") as list_jobs,
    ):
        list_jobs.return_value = [_planned_job_row(enabled=False)]
        r = client.patch("/api/v1/ops/scheduler/jobs/purge_stale_cache", json={"enabled": False})
    assert r.status_code == 200
    p.assert_called_once()
    assert r.json()["data"]["enabled"] is False


def test_patch_unknown_job_returns_404() -> None:
    client = _api_client()
    with patch("app.services.ops.scheduler.patch_job_enabled") as p:
        r = client.patch("/api/v1/ops/scheduler/jobs/unknown_job_xyz", json={"enabled": False})
    assert r.status_code == 404
    p.assert_not_called()


def test_patch_process_job_enabled_true_returns_400() -> None:
    client = _api_client()
    with patch("app.services.ops.scheduler.patch_job_enabled") as p:
        r = client.patch("/api/v1/ops/scheduler/jobs/collect_quotes", json={"enabled": True})
    assert r.status_code == 400
    p.assert_not_called()


def test_run_process_job_returns_400() -> None:
    client = _api_client()
    r = client.post("/api/v1/ops/scheduler/jobs/collect_quotes/run")
    assert r.status_code == 400

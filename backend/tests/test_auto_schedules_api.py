from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
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


def _api_client(*, db: MagicMock | None = None, user: User | None = None) -> TestClient:
    app = create_app()
    u = user or _make_user()
    session = db if db is not None else MagicMock()

    def override_db():  # type: ignore[no-untyped-def]
        yield session

    def override_user():  # type: ignore[no-untyped-def]
        return u

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user
    return TestClient(app)


def _row(*, id_: int = 7) -> SimpleNamespace:
    return SimpleNamespace(
        id=id_,
        user_id="u1",
        name="盘中自动",
        recipe_id="intraday_multi",
        days_of_week="mon-fri",
        times=["09:35", "14:00"],
        enabled=True,
        last_run_at=None,
        last_message=None,
        last_success=None,
        created_at="2026-08-19 10:00:00",
        updated_at="2026-08-19 10:00:00",
    )


def test_list_empty() -> None:
    db = MagicMock()
    db.scalars.return_value = []
    client = _api_client(db=db)
    resp = client.get("/api/v1/auto-schedules")
    assert resp.status_code == 200
    assert resp.json()["data"]["items"] == []


def test_create_valid() -> None:
    db = MagicMock()
    row = _row()
    with patch(
        "app.repositories.auto_schedule.AutoScheduleRepository.create_task", return_value=row
    ) as create:
        client = _api_client(db=db)
        resp = client.post(
            "/api/v1/auto-schedules",
            json={
                "name": "盘中自动",
                "recipe_id": "intraday_multi",
                "days_of_week": "mon-fri",
                "times": ["09:35", "14:00", "09:35"],
            },
        )
    assert resp.status_code == 200
    assert resp.json()["data"]["id"] == 7
    create.assert_called_once()
    assert create.call_args.kwargs["times"] == ["09:35", "14:00"]


def test_create_invalid_recipe() -> None:
    db = MagicMock()
    client = _api_client(db=db)
    resp = client.post(
        "/api/v1/auto-schedules",
        json={"name": "x", "recipe_id": "nope", "days_of_week": "mon-fri", "times": ["09:35"]},
    )
    assert resp.status_code == 400


def test_create_invalid_time() -> None:
    db = MagicMock()
    client = _api_client(db=db)
    resp = client.post(
        "/api/v1/auto-schedules",
        json={"name": "x", "recipe_id": "intraday_multi", "days_of_week": "mon-fri", "times": ["9:35"]},
    )
    assert resp.status_code == 400


def test_update_ok() -> None:
    db = MagicMock()
    row = _row()
    with (
        patch("app.repositories.auto_schedule.AutoScheduleRepository.get", return_value=row),
        patch(
            "app.repositories.auto_schedule.AutoScheduleRepository.update_task", return_value=row
        ) as update,
    ):
        client = _api_client(db=db)
        resp = client.patch("/api/v1/auto-schedules/7", json={"times": ["09:35"]})
    assert resp.status_code == 200
    assert resp.json()["data"]["id"] == 7
    assert update.call_args.args == (7, {"times": ["09:35"]})


def test_update_not_found() -> None:
    db = MagicMock()
    with patch("app.repositories.auto_schedule.AutoScheduleRepository.get", return_value=None):
        client = _api_client(db=db)
        resp = client.patch("/api/v1/auto-schedules/99", json={"name": "x"})
    assert resp.status_code == 404


def test_set_enabled() -> None:
    db = MagicMock()
    row = _row()
    row.enabled = False
    with (
        patch("app.repositories.auto_schedule.AutoScheduleRepository.get", return_value=row),
        patch(
            "app.repositories.auto_schedule.AutoScheduleRepository.update_task", return_value=row
        ) as update,
    ):
        client = _api_client(db=db)
        resp = client.patch("/api/v1/auto-schedules/7/enabled", json={"enabled": False})
    assert resp.status_code == 200
    assert resp.json()["data"]["enabled"] is False
    assert update.call_args.args == (7, {"enabled": False})


def test_delete_ok() -> None:
    db = MagicMock()
    with patch("app.repositories.auto_schedule.AutoScheduleRepository.get", return_value=_row()):
        client = _api_client(db=db)
        resp = client.delete("/api/v1/auto-schedules/7")
    assert resp.status_code == 200
    assert resp.json()["data"]["ok"] is True


def test_delete_not_found() -> None:
    db = MagicMock()
    with patch("app.repositories.auto_schedule.AutoScheduleRepository.get", return_value=None):
        client = _api_client(db=db)
        resp = client.delete("/api/v1/auto-schedules/99")
    assert resp.status_code == 404

"""情绪周期阈值 API 单测。"""

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
from app.services.emotion_cycle import DEFAULT_THRESHOLDS


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


def _api_client() -> TestClient:
    user = _make_user()
    app = create_app()

    def override_db():  # type: ignore[no-untyped-def]
        yield MagicMock()

    def override_user():  # type: ignore[no-untyped-def]
        return user

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user
    return TestClient(app)


def test_get_emotion_thresholds_default() -> None:
    client = _api_client()
    with patch(
        "app.api.v1.market.emotion_thresholds_svc.load_thresholds",
        return_value=(DEFAULT_THRESHOLDS, True),
    ):
        resp = client.get("/api/v1/market/emotion-cycle/thresholds")
    assert resp.status_code == 200
    body = resp.json()
    assert body["is_default"] is True
    assert body["recession_limit_down"] == DEFAULT_THRESHOLDS.recession_limit_down


def test_put_emotion_thresholds() -> None:
    client = _api_client()
    updated = DEFAULT_THRESHOLDS
    with patch(
        "app.api.v1.market.emotion_thresholds_svc.save_thresholds",
        return_value=updated,
    ) as save:
        resp = client.put(
            "/api/v1/market/emotion-cycle/thresholds",
            json={"recession_limit_down": 25},
        )
    assert resp.status_code == 200
    save.assert_called_once()
    body = resp.json()
    assert body["is_default"] is False


def test_reset_emotion_thresholds() -> None:
    client = _api_client()
    with patch(
        "app.api.v1.market.emotion_thresholds_svc.reset_thresholds",
        return_value=DEFAULT_THRESHOLDS,
    ) as reset:
        resp = client.post("/api/v1/market/emotion-cycle/thresholds/reset")
    assert resp.status_code == 200
    reset.assert_called_once()
    body = resp.json()
    assert body["is_default"] is True

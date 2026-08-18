"""notify_log 服务与 API 单测。"""

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
from app.services.content.notify_log import clamp_limit, list_notify_log, parse_payload


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


def test_clamp_limit() -> None:
    assert clamp_limit(None) == 50
    assert clamp_limit(0) == 1
    assert clamp_limit(200) == 100
    assert clamp_limit(50) == 50


def test_parse_payload_ok() -> None:
    assert parse_payload('{"a": 1}') == {"a": 1}


def test_parse_payload_raw() -> None:
    assert parse_payload("not-json") == {"_raw": "not-json"}


def test_parse_payload_non_dict() -> None:
    assert parse_payload("[1, 2]") == {"_raw": [1, 2]}


def test_list_empty() -> None:
    db = MagicMock()
    db.scalars.return_value = []
    out = list_notify_log(db, "u1", limit=50)
    assert out.items == []
    assert out.count == 0
    assert out.limit == 50


def test_list_maps_payload() -> None:
    db = MagicMock()
    db.scalars.return_value = [
        SimpleNamespace(
            id="1",
            event_type="test",
            channel="feishu",
            payload_json='{"x": 1}',
            status="ok",
            error="",
            created_at="2026-08-07 10:00:00",
        )
    ]
    out = list_notify_log(db, "u1", limit=10)
    assert out.items[0].payload == {"x": 1}
    assert out.items[0].event_type == "test"


def test_api_notify_log_ok() -> None:
    user = _make_user()
    db = MagicMock()
    mock_out = {
        "items": [
            {
                "id": "1",
                "event_type": "risk_alert",
                "channel": "feishu",
                "status": "ok",
                "error": "",
                "created_at": "2026-08-07 10:00:00",
                "payload": {"symbol": "600519.SSE"},
            }
        ],
        "limit": 10,
        "count": 1,
    }
    client = _api_client(db=db, user=user)
    with patch("app.api.v1.watchlist.notify_log.list_notify_log", return_value=mock_out) as mock_list:
        resp = client.get("/api/v1/watchlist/notify-log?limit=10")
    assert resp.status_code == 200
    body = resp.json()
    assert body["data"]["count"] == 1
    assert body["data"]["limit"] == 10
    assert body["data"]["items"][0]["event_type"] == "risk_alert"
    assert body["data"]["items"][0]["payload"] == {"symbol": "600519.SSE"}
    mock_list.assert_called_once_with(db, str(user.id), limit=10)

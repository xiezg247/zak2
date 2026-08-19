"""channels API 单测。"""

from __future__ import annotations

import json
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


def _channel_row(*, id_: str = "c1", name: str = "组群", webhook: str = "https://open.feishu.cn/x", enabled: bool = True) -> SimpleNamespace:
    return SimpleNamespace(
        id=id_,
        user_id="u1",
        channel_type="feishu",
        name=name,
        config_json=json.dumps({"webhook_url": webhook}),
        enabled=enabled,
        created_at="2026-08-19 10:00:00",
        updated_at="2026-08-19 10:00:00",
    )


def test_list_channels_empty() -> None:
    db = MagicMock()
    db.scalars.return_value = []
    client = _api_client(db=db)
    resp = client.get("/api/v1/channels")
    assert resp.status_code == 200
    assert resp.json()["data"]["items"] == []


def test_list_channels_maps_out() -> None:
    db = MagicMock()
    db.scalars.return_value = [_channel_row()]
    client = _api_client(db=db)
    resp = client.get("/api/v1/channels")
    assert resp.status_code == 200
    item = resp.json()["data"]["items"][0]
    assert item["name"] == "组群"
    assert item["channel_type"] == "feishu"
    assert item["webhook_url"] == "https://open.feishu.cn/x"
    assert item["enabled"] is True


def test_create_channel_valid() -> None:
    db = MagicMock()
    row = _channel_row(id_="new-id", name="新群", webhook="https://open.feishu.cn/y")
    db.add.side_effect = None
    with patch("app.repositories.channel.ChannelRepository.create_channel", return_value=row) as create:
        client = _api_client(db=db)
        resp = client.post(
            "/api/v1/channels",
            json={"name": "新群", "webhook_url": "https://open.feishu.cn/y", "enabled": True},
        )
    assert resp.status_code == 200
    assert resp.json()["data"]["name"] == "新群"
    create.assert_called_once()
    assert create.call_args.kwargs["name"] == "新群"


def test_create_channel_missing_name() -> None:
    db = MagicMock()
    client = _api_client(db=db)
    resp = client.post("/api/v1/channels", json={"name": "", "webhook_url": "https://open.feishu.cn/y"})
    assert resp.status_code == 422


def test_create_channel_missing_webhook() -> None:
    db = MagicMock()
    client = _api_client(db=db)
    resp = client.post("/api/v1/channels", json={"name": "组群", "webhook_url": ""})
    assert resp.status_code == 422


def test_update_channel() -> None:
    db = MagicMock()
    row = _channel_row(id_="c1", name="改名后")
    with patch("app.repositories.channel.ChannelRepository.update_channel", return_value=row) as update:
        client = _api_client(db=db)
        resp = client.patch("/api/v1/channels/c1", json={"name": "改名后", "enabled": False})
    assert resp.status_code == 200
    assert resp.json()["data"]["name"] == "改名后"
    update.assert_called_once()
    assert update.call_args.args[0] == "c1"
    assert update.call_args.args[1] == {"name": "改名后", "enabled": False}


def test_update_channel_not_found() -> None:
    db = MagicMock()
    with patch("app.repositories.channel.ChannelRepository.get", return_value=None):
        client = _api_client(db=db)
        resp = client.patch("/api/v1/channels/nope", json={"name": "x"})
    assert resp.status_code == 404


def test_delete_channel() -> None:
    db = MagicMock()
    with patch("app.repositories.channel.ChannelRepository.get", return_value=_channel_row()):
        client = _api_client(db=db)
        resp = client.delete("/api/v1/channels/c1")
    assert resp.status_code == 200
    assert resp.json()["data"]["ok"] is True


def test_delete_channel_not_found() -> None:
    db = MagicMock()
    with patch("app.repositories.channel.ChannelRepository.get", return_value=None):
        client = _api_client(db=db)
        resp = client.delete("/api/v1/channels/nope")
    assert resp.status_code == 404


def test_test_channel_ok() -> None:
    db = MagicMock()
    with (
        patch("app.repositories.channel.ChannelRepository.get", return_value=_channel_row()),
        patch("app.api.v1.channels.notify_delivery.send_to_channel", return_value=(True, "")) as send,
    ):
        client = _api_client(db=db)
        resp = client.post("/api/v1/channels/c1/test")
    assert resp.status_code == 200
    body = resp.json()["data"]
    assert body["ok"] is True
    assert "成功" in body["message"]
    send.assert_called_once()
    assert send.call_args.args[0] is db


def test_test_channel_failed() -> None:
    db = MagicMock()
    with (
        patch("app.repositories.channel.ChannelRepository.get", return_value=_channel_row()),
        patch("app.api.v1.channels.notify_delivery.send_to_channel", return_value=(False, "HTTP 500")) as send,
    ):
        client = _api_client(db=db)
        resp = client.post("/api/v1/channels/c1/test")
    assert resp.status_code == 200
    body = resp.json()["data"]
    assert body["ok"] is False
    assert body["message"] == "HTTP 500"
    send.assert_called_once()


def test_test_channel_not_found() -> None:
    db = MagicMock()
    with patch("app.repositories.channel.ChannelRepository.get", return_value=None):
        client = _api_client(db=db)
        resp = client.post("/api/v1/channels/nope/test")
    assert resp.status_code == 404

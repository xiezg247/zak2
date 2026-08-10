from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import hash_password
from app.main import create_app
from app.models.user import User


class _FakeScalarResult:
    def __init__(self, value):  # type: ignore[no-untyped-def]
        self._value = value

    def scalar(self, _statement=None):  # type: ignore[no-untyped-def]
        return self._value


class _FakeSession:
    def __init__(self, user: User | None) -> None:
        self._user = user

    def scalar(self, statement):  # type: ignore[no-untyped-def]
        # 粗略：login 按 username；me/deps 按 id
        _ = statement
        return self._user

    def close(self) -> None:
        return None


def _make_user(*, active: bool = True) -> User:
    now = datetime.now(UTC)
    return User(
        id=str(uuid4()),
        username="demo",
        display_name="Demo",
        password_hash=hash_password("demo-pass"),
        is_active=active,
        created_at=now,
        updated_at=now,
    )


def test_login_and_me() -> None:
    user = _make_user()
    app = create_app()

    def override_db():  # type: ignore[no-untyped-def]
        yield _FakeSession(user)

    app.dependency_overrides[get_db] = override_db
    client = TestClient(app)

    bad = client.post("/api/v1/auth/login", json={"username": "demo", "password": "wrong"})
    assert bad.status_code == 401

    ok = client.post("/api/v1/auth/login", json={"username": "demo", "password": "demo-pass"})
    assert ok.status_code == 200
    token = ok.json()["access_token"]

    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["username"] == "demo"


def test_disabled_user_forbidden() -> None:
    user = _make_user(active=False)
    app = create_app()

    def override_db():  # type: ignore[no-untyped-def]
        yield _FakeSession(user)

    app.dependency_overrides[get_db] = override_db
    client = TestClient(app)
    resp = client.post("/api/v1/auth/login", json={"username": "demo", "password": "demo-pass"})
    assert resp.status_code == 403

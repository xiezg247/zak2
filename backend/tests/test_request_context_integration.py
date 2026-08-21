"""集成：鉴权后 user_id 写入上下文；未捕获异常日志携带上下文。"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from unittest.mock import MagicMock

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.api.errors import register_exception_handlers
from app.core.db import get_db
from app.core.request_context import get_request_context
from app.core.request_context_middleware import RequestContextMiddleware
from app.core.security import create_access_token
from app.main import create_app
from app.models.user import User


def _app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(RequestContextMiddleware)
    register_exception_handlers(app)

    @app.get("/boom")
    def boom() -> None:
        raise RuntimeError("kaboom")

    @app.get("/context")
    def ctx() -> dict | None:
        c = get_request_context()
        return {"request_id": c.request_id, "user_id": c.user_id} if c else None

    return app


def test_unhandled_exception_log_has_context(caplog) -> None:
    client = TestClient(_app())
    with caplog.at_level(logging.ERROR, logger="app.api.errors"):
        resp = client.get("/boom", headers={"X-Request-ID": "req-1"})
    assert resp.status_code == 500
    assert resp.headers["X-Request-ID"] == "req-1"
    assert any("req-1" in r.message for r in caplog.records)
    assert any("/boom" in r.message for r in caplog.records)


def test_middleware_runs_before_handlers() -> None:
    client = TestClient(_app())
    resp = client.get("/context")
    body = resp.json()
    assert body["request_id"] == resp.headers["X-Request-ID"]
    assert body["user_id"] is None


def test_auth_sets_user_id_from_token() -> None:
    """真实 JWT 走 get_current_user → set_user_id 接线，断言上下文 user_id 与 token sub 一致。"""
    now = datetime.now(UTC)
    app = create_app()
    db = MagicMock()
    db.scalar.return_value = User(
        id="u-test",
        username="tester",
        display_name="Tester",
        password_hash="x",
        is_active=True,
        created_at=now,
        updated_at=now,
    )

    def override_db():  # type: ignore[no-untyped-def]
        yield db

    app.dependency_overrides[get_db] = override_db

    @app.get("/api/v1/_whoami")
    def whoami(user: User = Depends(get_current_user)) -> dict:
        ctx = get_request_context()
        return {"user_id": ctx.user_id if ctx else None, "path_user": user.id}

    token = create_access_token(user_id="u-test", username="tester")
    client = TestClient(app)
    resp = client.get("/api/v1/_whoami", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json() == {"user_id": "u-test", "path_user": "u-test"}
    assert resp.headers["X-Request-ID"]  # 正常路径同样回显

"""集成：鉴权后 user_id 写入上下文；未捕获异常日志携带上下文。"""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.errors import register_exception_handlers
from app.core.request_context import get_request_context
from app.core.request_context_middleware import RequestContextMiddleware


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
    assert any("req-1" in r.message for r in caplog.records)
    assert any("/boom" in r.message for r in caplog.records)


def test_middleware_runs_before_handlers() -> None:
    client = TestClient(_app())
    resp = client.get("/context")
    body = resp.json()
    assert body["request_id"] == resp.headers["X-Request-ID"]
    assert body["user_id"] is None

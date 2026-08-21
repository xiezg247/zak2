"""中间件集成测试：request_id 回显 + 上下文写入。"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.request_context import get_request_id
from app.core.request_context_middleware import RequestContextMiddleware


def _app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(RequestContextMiddleware)

    @app.get("/echo")
    def echo() -> dict[str, str]:
        return {"request_id": get_request_id()}

    return app


def test_echo_header_passthrough() -> None:
    client = TestClient(_app())
    resp = client.get("/echo", headers={"X-Request-ID": "client-abc"})
    assert resp.status_code == 200
    assert resp.headers["X-Request-ID"] == "client-abc"
    assert resp.json() == {"request_id": "client-abc"}


def test_generates_and_echoes_when_absent() -> None:
    client = TestClient(_app())
    resp = client.get("/echo")
    assert resp.status_code == 200
    rid = resp.headers["X-Request-ID"]
    assert len(rid) == 12 and rid.isalnum()
    assert resp.json() == {"request_id": rid}


def test_invalid_header_generates_new() -> None:
    client = TestClient(_app())
    resp = client.get("/echo", headers={"X-Request-ID": "bad value!"})
    rid = resp.headers["X-Request-ID"]
    assert len(rid) == 12 and rid.isalnum()


def test_context_reset_after_request() -> None:
    from app.core.request_context import get_request_context

    client = TestClient(_app())
    client.get("/echo")
    assert get_request_context() is None

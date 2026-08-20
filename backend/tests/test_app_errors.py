from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.errors import register_exception_handlers
from app.core.errors import NotFound, RateLimited, ValidationFailed


def _client() -> TestClient:
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/nf")
    def nf() -> None:
        raise NotFound("渠道不存在")

    @app.get("/vf")
    def vf() -> None:
        raise ValidationFailed("没有需要更新的字段")

    @app.get("/rl")
    def rl() -> None:
        raise RateLimited("尝试次数过多，请稍后再试")

    return TestClient(app, raise_server_exceptions=False)


def test_not_found_maps_404() -> None:
    resp = _client().get("/nf")
    assert resp.status_code == 404
    body = resp.json()
    assert body["code"] == 404
    assert body["message"] == "渠道不存在"
    assert body["detail"] == "渠道不存在"
    assert body["data"] is None


def test_validation_failed_maps_400() -> None:
    resp = _client().get("/vf")
    assert resp.status_code == 400
    assert resp.json()["message"] == "没有需要更新的字段"


def test_rate_limited_maps_429() -> None:
    resp = _client().get("/rl")
    assert resp.status_code == 429
    assert "尝试次数过多" in resp.json()["message"]

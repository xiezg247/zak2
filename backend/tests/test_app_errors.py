from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.errors import register_exception_handlers
from app.core.errors import (
    Conflict,
    NotFound,
    RateLimited,
    Unavailable,
    UpstreamFailed,
    ValidationFailed,
)


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

    @app.get("/up")
    def up() -> None:
        raise UpstreamFailed("上游失败")

    @app.get("/cf")
    def cf() -> None:
        raise Conflict("已在自选中")

    @app.get("/ua")
    def ua() -> None:
        raise Unavailable("Redis 不可用")

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


def test_upstream_failed_maps_502() -> None:
    resp = _client().get("/up")
    assert resp.status_code == 502
    assert resp.json()["message"] == "上游失败"


def test_conflict_maps_409() -> None:
    resp = _client().get("/cf")
    assert resp.status_code == 409
    assert resp.json()["message"] == "已在自选中"


def test_unavailable_maps_503() -> None:
    resp = _client().get("/ua")
    assert resp.status_code == 503
    assert "Redis" in resp.json()["message"]

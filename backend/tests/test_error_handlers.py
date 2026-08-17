from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.settings import Settings
from app.main import create_app


def test_production_requires_custom_jwt_secret(monkeypatch) -> None:
    monkeypatch.delenv("JWT_SECRET", raising=False)
    with pytest.raises(ValueError, match="JWT_SECRET"):
        Settings(_env_file=None, environment="production")


def test_development_allows_default_secret(monkeypatch) -> None:
    monkeypatch.delenv("JWT_SECRET", raising=False)
    s = Settings(_env_file=None, environment="development")
    assert s.jwt_secret


def test_http_exception_unified_body() -> None:
    client = TestClient(create_app())
    resp = client.get("/api/v1/does-not-exist")
    assert resp.status_code == 404
    body = resp.json()
    assert body["code"] == 404
    assert body["message"]
    assert body["detail"] == "Not Found"
    assert body["data"] is None


def test_validation_error_unified_body() -> None:
    client = TestClient(create_app())
    resp = client.post("/api/v1/auth/login", json={})
    assert resp.status_code == 422
    body = resp.json()
    assert body["code"] == 422
    assert body["message"]
    assert body["data"] is None


def test_unhandled_exception_returns_500_envelope() -> None:
    app = create_app()

    @app.get("/boom")
    def boom() -> None:
        raise RuntimeError("boom")

    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/boom")
    assert resp.status_code == 500
    body = resp.json()
    assert body["code"] == 500
    assert body["message"] == "服务器内部错误"
    assert body["detail"] == "服务器内部错误"
    assert body["data"] is None

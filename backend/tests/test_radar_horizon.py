"""radar_horizon 读 cache 与 GET /radar/horizon 单测。"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from unittest.mock import MagicMock
from uuid import uuid4

from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.core.db import get_db
from app.core.security import hash_password
from app.main import create_app
from app.models.user import User
from app.services.radar_horizon import load_horizon


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
    mock_db = db or MagicMock()

    def override_db():  # type: ignore[no-untyped-def]
        yield mock_db

    def override_user():  # type: ignore[no-untyped-def]
        return u

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user
    return TestClient(app)


def test_load_horizon_no_cache_row() -> None:
    db = MagicMock()
    result = MagicMock()
    result.mappings.return_value.first.return_value = None
    db.execute.return_value = result

    out = load_horizon(db)
    assert out.empty is True
    assert out.rows == []
    assert out.computed_at is None
    assert out.label == "启发式展望（基于共振）"


def test_load_horizon_with_rows() -> None:
    db = MagicMock()
    result = MagicMock()
    result.mappings.return_value.first.return_value = {
        "variant": "default",
        "rows_json": json.dumps(
            [
                {
                    "vt_symbol": "600519.SSE",
                    "name": "茅台",
                    "resonance_score": 1.5,
                    "card_count": 2,
                    "card_titles": ["T"],
                    "change_pct": 1.0,
                    "last_price": 100.0,
                    "seal_time_label": "",
                }
            ],
            ensure_ascii=False,
        ),
        "scanned_total": 10,
        "refined_total": 1,
        "strategy_key": "resonance_heuristic",
        "computed_at": "2026-08-12T09:00:00+00:00",
    }
    db.execute.return_value = result

    out = load_horizon(db)
    assert out.empty is False
    assert out.variant == "default"
    assert out.strategy_key == "resonance_heuristic"
    assert out.computed_at == "2026-08-12T09:00:00+00:00"
    assert out.scanned_total == 10
    assert out.refined_total == 1
    assert len(out.rows) == 1
    assert out.rows[0].vt_symbol == "600519.SSE"
    assert out.rows[0].resonance_score == 1.5


def test_get_radar_horizon_missing_cache_returns_200() -> None:
    db = MagicMock()
    result = MagicMock()
    result.mappings.return_value.first.return_value = None
    db.execute.return_value = result

    client = _api_client(db=db)
    resp = client.get("/api/v1/radar/horizon")
    assert resp.status_code == 200
    body = resp.json()
    assert body["data"]["empty"] is True
    assert body["data"]["rows"] == []
    assert body["data"]["computed_at"] is None
    assert body["data"]["label"] == "启发式展望（基于共振）"

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.core.db import get_db
from app.core.security import hash_password
from app.main import create_app
from app.models.user import User
from app.services import fundamentals as fund


def _client() -> TestClient:
    app = create_app()
    now = datetime.now(UTC)
    u = User(
        id=str(uuid4()),
        username="demo",
        display_name="Demo",
        password_hash=hash_password("x"),
        is_active=True,
        created_at=now,
        updated_at=now,
    )

    def override_db():
        yield MagicMock()

    def override_user():
        return u

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user
    return TestClient(app)


def test_api_fundamentals_ok() -> None:
    client = _client()
    fake = {
        "vt_symbol": "600519.SSE",
        "ts_code": "600519.SH",
        "snapshot": None,
        "sync": None,
        "disclosures": [],
    }
    with patch("app.api.v1.watchlist.fundamentals_svc.get_fundamentals", return_value=fake) as g:
        r = client.get("/api/v1/watchlist/items/600519.SSE/fundamentals")
    assert r.status_code == 200
    assert r.json()["data"]["ts_code"] == "600519.SH"
    g.assert_called_once()


def test_api_fundamentals_bad_symbol() -> None:
    client = _client()
    with patch(
        "app.api.v1.watchlist.fundamentals_svc.get_fundamentals",
        side_effect=HTTPException(status_code=400, detail="代码为空"),
    ):
        r = client.get("/api/v1/watchlist/items/%20/fundamentals")
    assert r.status_code == 400


def test_invalid_vt_400() -> None:
    db = MagicMock()
    with pytest.raises(HTTPException) as ei:
        fund.get_fundamentals(db, "")
    assert ei.value.status_code == 400


def test_empty_db_returns_nulls() -> None:
    db = MagicMock()
    snap = MagicMock()
    snap.mappings.return_value.first.return_value = None
    meta = MagicMock()
    meta.mappings.return_value.first.return_value = None
    disc = MagicMock()
    disc.mappings.return_value.all.return_value = []
    db.execute.side_effect = [snap, meta, disc]
    out = fund.get_fundamentals(db, "600519.SSE")
    assert out["vt_symbol"] == "600519.SSE"
    assert out["ts_code"] == "600519.SH"
    assert out["snapshot"] is None
    assert out["sync"] is None
    assert out["disclosures"] == []


def test_snapshot_and_disclosures_mapped() -> None:
    db = MagicMock()
    snap_row = {
        "end_date": "20251231",
        "revenue": 1e9,
        "net_income": 1e8,
        "revenue_yoy": 0.1,
        "net_income_yoy": 0.2,
        "roe": 0.15,
        "debt_ratio": 0.4,
    }
    sync_row = {
        "last_sync_at": "t1",
        "latest_end_date": "20251231",
        "periods_count": 4,
        "sync_status": "ok",
        "error_message": "",
    }
    disc_rows = [
        {"end_date": "20251231", "pre_date": "20260110", "ann_date": "", "actual_date": ""},
        {"end_date": "20250930", "pre_date": "", "ann_date": "20251020", "actual_date": ""},
        {"end_date": "20250630", "pre_date": "", "ann_date": "", "actual_date": "20250715"},
        {"end_date": "20250331", "pre_date": "", "ann_date": "", "actual_date": ""},
    ]
    snap = MagicMock()
    snap.mappings.return_value.first.return_value = snap_row
    meta = MagicMock()
    meta.mappings.return_value.first.return_value = sync_row
    disc = MagicMock()
    disc.mappings.return_value.all.return_value = disc_rows[:3]
    db.execute.side_effect = [snap, meta, disc]
    out = fund.get_fundamentals(db, "600519.SSE")
    assert out["snapshot"]["end_date"] == "20251231"
    assert out["snapshot"]["roe"] == 0.15
    assert out["sync"]["periods_count"] == 4
    assert len(out["disclosures"]) == 3
    assert out["disclosures"][0]["end_date"] == "20251231"

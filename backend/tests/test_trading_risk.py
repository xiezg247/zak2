from __future__ import annotations

import json
from datetime import UTC, datetime
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.core.db import get_db
from app.core.security import hash_password
from app.main import create_app
from app.models.user import User
from app.services import trading_risk as tr


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


def test_normalize_prefs_defaults_bad_values() -> None:
    out = tr.normalize_prefs(
        {
            "total_capital": -1,
            "stop_loss_pct": 0.9,
            "caution_float_pct": 1.0,
            "realized_pnl_today": 100.0,
        }
    )
    assert out["total_capital"] is None
    assert out["stop_loss_pct"] == tr.DEFAULT_STOP_LOSS_PCT
    assert out["caution_float_pct"] == tr.DEFAULT_CAUTION_FLOAT_PCT
    assert out["realized_pnl_today"] == 100.0


def test_normalize_prefs_keeps_valid() -> None:
    out = tr.normalize_prefs(
        {
            "total_capital": 100000.0,
            "stop_loss_pct": 0.08,
            "caution_float_pct": -3.5,
        }
    )
    assert out["total_capital"] == 100000.0
    assert out["stop_loss_pct"] == 0.08
    assert out["caution_float_pct"] == -3.5


def test_save_rejects_bad_total_capital() -> None:
    db = MagicMock()
    with pytest.raises(ValueError, match="总资金"):
        tr.save_trading_risk_prefs(db, "uid", {"total_capital": 0})


def test_save_rejects_bad_stop_loss() -> None:
    db = MagicMock()
    with pytest.raises(ValueError, match="止损"):
        tr.save_trading_risk_prefs(db, "uid", {"stop_loss_pct": 0.6})


def test_save_rejects_bad_caution() -> None:
    db = MagicMock()
    with pytest.raises(ValueError, match="浮亏"):
        tr.save_trading_risk_prefs(db, "uid", {"caution_float_pct": 0})


def test_save_upserts_and_returns_normalized() -> None:
    db = MagicMock()
    db.execute.return_value.scalar.return_value = None
    out = tr.save_trading_risk_prefs(
        db,
        "550e8400-e29b-41d4-a716-446655440000",
        {"total_capital": 200000, "stop_loss_pct": 0.1, "caution_float_pct": -4.0},
    )
    assert out["total_capital"] == 200000
    assert out["stop_loss_pct"] == 0.1
    assert out["caution_float_pct"] == -4.0
    db.execute.assert_called()
    db.commit.assert_called_once()
    call_params = db.execute.call_args[0][1]
    payload = json.loads(call_params["val"])
    assert payload["total_capital"] == 200000


def test_load_returns_defaults_when_missing() -> None:
    db = MagicMock()
    db.execute.return_value.scalar.return_value = None
    out = tr.load_trading_risk_prefs(db, "uid")
    assert out["stop_loss_pct"] == tr.DEFAULT_STOP_LOSS_PCT
    assert out["caution_float_pct"] == tr.DEFAULT_CAUTION_FLOAT_PCT
    assert out["total_capital"] is None


def test_compute_actual_position_pct() -> None:
    assert tr.compute_actual_position_pct(12000, 100000) == pytest.approx(0.12)
    assert tr.compute_actual_position_pct(12000, None) is None
    assert tr.compute_actual_position_pct(12000, 0) is None


def test_normalize_plan_max_pct() -> None:
    assert tr.normalize_plan_max_pct(0.3) == pytest.approx(0.3)
    assert tr.normalize_plan_max_pct(30) == pytest.approx(0.3)
    assert tr.normalize_plan_max_pct(0) is None
    assert tr.normalize_plan_max_pct(-1) is None


def test_get_trading_risk_api_defaults() -> None:
    db = MagicMock()
    db.execute.return_value.scalar.return_value = None
    client = _api_client(db=db)
    resp = client.get("/api/v1/watchlist/trading-risk")
    assert resp.status_code == 200
    body = resp.json()
    assert body["stop_loss_pct"] == tr.DEFAULT_STOP_LOSS_PCT
    assert body["caution_float_pct"] == tr.DEFAULT_CAUTION_FLOAT_PCT
    assert body["total_capital"] is None


def test_put_trading_risk_api_ok() -> None:
    db = MagicMock()
    db.execute.return_value.scalar.return_value = None
    client = _api_client(db=db)
    resp = client.put(
        "/api/v1/watchlist/trading-risk",
        json={"total_capital": 50000, "stop_loss_pct": 0.06, "caution_float_pct": -6.0},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_capital"] == 50000
    assert body["stop_loss_pct"] == 0.06


def test_put_trading_risk_api_bad_value_400() -> None:
    client = _api_client()
    resp = client.put(
        "/api/v1/watchlist/trading-risk",
        json={"stop_loss_pct": 0.0},
    )
    assert resp.status_code == 400
    assert "止损" in resp.json()["detail"]

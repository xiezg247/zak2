"""limit-list API / list_limit_list / 雷达梯队 attach 单测。"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.db import get_db
from app.core.security import hash_password
from app.main import create_app
from app.models.user import User
from app.api.deps import get_current_user
from app.services.limit_list_store import list_limit_list
from app.services.radar import _synth_limit_ladder


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


def test_list_limit_list_empty_no_raise() -> None:
    db = MagicMock()

    def _execute(stmt, params=None):  # noqa: ANN001
        result = MagicMock()
        sql = str(stmt)
        if "CREATE TABLE" in sql:
            return result
        if "FROM app.limit_list_daily" in sql:
            result.mappings.return_value = []
            return result
        return result

    db.execute.side_effect = _execute
    from app.services import tushare_client as ts

    with (
        patch("app.services.limit_list_store.latest_open_yyyymmdd", return_value="20240805"),
        patch(
            "app.services.limit_list_store.ts.require_token",
            side_effect=ts.TushareNotConfiguredError("missing"),
        ),
    ):
        out = list_limit_list(db, "20240805", lazy_fetch=True)
    assert out["trade_date"] == "20240805"
    assert out["total"] == 0
    assert out["rows"] == []


def test_list_limit_list_returns_rows() -> None:
    db = MagicMock()

    def _execute(stmt, params=None):  # noqa: ANN001
        result = MagicMock()
        sql = str(stmt)
        if "CREATE TABLE" in sql:
            return result
        if "FROM app.limit_list_daily" in sql and "SELECT trade_date" in sql:
            result.mappings.return_value = [
                {
                    "trade_date": "20240805",
                    "vt_symbol": "SHSE.600519",
                    "ts_code": "600519.SH",
                    "name": "茅台",
                    "limit_times": 2.0,
                    "first_time": "0935",
                    "last_time": "0935",
                    "fd_amount": 1.0,
                    "open_times": 0.0,
                    "strth": 80.0,
                    "updated_at": "2024-08-05T10:00:00+00:00",
                }
            ]
            return result
        return result

    db.execute.side_effect = _execute
    out = list_limit_list(db, "20240805", lazy_fetch=False)
    assert out["total"] == 1
    assert out["rows"][0]["vt_symbol"] == "SHSE.600519"
    assert out["rows"][0]["seal_time_label"] == "09:35 封板"
    assert out["rows"][0]["seal_time_score"] == 1.0


def test_get_limit_list_api_empty() -> None:
    user = _make_user()
    app = create_app()

    def override_db():  # type: ignore[no-untyped-def]
        yield MagicMock()

    def override_user():  # type: ignore[no-untyped-def]
        return user

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user
    client = TestClient(app)

    with patch(
        "app.api.v1.market.list_limit_list",
        return_value={"trade_date": "20240805", "total": 0, "rows": []},
    ):
        resp = client.get("/api/v1/market/limit-list?trade_date=20240805")
    assert resp.status_code == 200
    body = resp.json()
    assert body["data"]["trade_date"] == "20240805"
    assert body["data"]["total"] == 0
    assert body["data"]["rows"] == []


def test_synth_limit_ladder_attaches_seal_fields() -> None:
    db = MagicMock()
    emotion = {
        "trade_date": "20240805",
        "max_limit_times": 3,
        "max_board_vt_symbol": "600519.SSE",
        "linked_board_vt_symbols": ["SZSE.000001"],
        "updated_at": "2024-08-05T10:00:00",
    }
    with (
        patch("app.services.radar.market_svc.load_emotion", return_value=emotion),
        patch(
            "app.services.limit_list_store.load_first_time_map",
            return_value={"SHSE.600519": "0930", "SZSE.000001": "1100"},
        ),
    ):
        card = _synth_limit_ladder(db)
    assert card.card_id == "discovery_limit_ladder"
    assert len(card.rows) == 2
    top = card.rows[0]
    assert top["vt_symbol"] == "600519.SSE"
    assert top["first_time"] == "0930"
    assert top["seal_time_label"] == "09:30 封板"
    linked = card.rows[1]
    assert linked["vt_symbol"] == "SZSE.000001"
    assert linked["first_time"] == "1100"
    assert linked["seal_time_label"] == "11:00 封板"

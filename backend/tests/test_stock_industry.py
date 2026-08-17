from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.core.db import get_db
from app.core.security import hash_password
from app.main import create_app
from app.models.user import User
from app.services import stock_industry as si
from app.services.quotes import QuoteRow


def _row(symbol: str, industry: str = "") -> QuoteRow:
    return QuoteRow(symbol=symbol, name="t", industry=industry)


def test_enrich_fills_empty_only() -> None:
    rows = [
        _row("SHSE.600519", ""),
        _row("SZSE.000001", "银行"),
        _row("SHSE.601318", ""),
    ]
    mapping = {"SHSE.600519": "白酒", "SZSE.000001": "覆盖不了", "SHSE.999999": "x"}
    n = si.enrich_empty_industries(rows, mapping)
    assert n == 1
    assert rows[0].industry == "白酒"
    assert rows[1].industry == "银行"
    assert rows[2].industry == ""


def test_load_industry_map_keys() -> None:
    db = MagicMock()
    db.execute.return_value.mappings.return_value = [
        {"symbol": "600519", "exchange": "SSE", "industry": "白酒"},
        {"symbol": "000001", "exchange": "SZSE", "industry": "银行"},
        {"symbol": "600000", "exchange": "SSE", "industry": ""},
    ]
    m = si.load_industry_map(db)
    assert m["SHSE.600519"] == "白酒"
    assert m["SZSE.000001"] == "银行"
    assert "SHSE.600000" not in m


def test_enrich_rows_from_db_none() -> None:
    assert si.enrich_rows_from_db(None, [_row("SHSE.1")]) == 0


def test_load_map_on_error_returns_empty() -> None:
    db = MagicMock()
    db.execute.side_effect = RuntimeError("no table")
    assert si.load_industry_map(db) == {}


def test_list_industry_names() -> None:
    db = MagicMock()
    db.execute.return_value.scalars.return_value.all.return_value = ["白酒", "银行"]
    assert si.list_industry_names(db) == ["白酒", "银行"]


def test_list_industry_names_on_error_returns_empty() -> None:
    db = MagicMock()
    db.execute.side_effect = RuntimeError("no table")
    assert si.list_industry_names(db) == []


def _make_user() -> User:
    now = datetime.now(UTC).isoformat()
    return User(
        id=str(uuid4()),
        username="demo",
        display_name="Demo",
        password_hash=hash_password("demo-pass"),
        is_active=True,
        created_at=now,
        updated_at=now,
    )


def _api_client(user: User | None = None) -> TestClient:
    app = create_app()
    u = user or _make_user()

    def override_db():  # type: ignore[no-untyped-def]
        yield MagicMock()

    def override_user():  # type: ignore[no-untyped-def]
        return u

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user
    return TestClient(app)


def test_industries_api() -> None:
    client = _api_client()
    with patch("app.api.v1.screener.list_industry_names", return_value=["白酒", "银行"]):
        resp = client.get("/api/v1/screener/industries")
    assert resp.status_code == 200
    assert resp.json()["data"] == {"items": ["白酒", "银行"]}

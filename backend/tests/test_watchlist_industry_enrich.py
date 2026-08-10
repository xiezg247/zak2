from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.api.v1 import watchlist as wl
from app.core.db import get_db
from app.core.security import hash_password
from app.main import create_app
from app.models.user import User
from app.services.quotes import QuoteRow


def _item(symbol: str = "600519", exchange: str = "SSE", name: str = "茅台", sort: int = 0):
    return SimpleNamespace(symbol=symbol, exchange=exchange, name=name, sort_order=sort)


def test_enrich_fills_empty_industry_from_db() -> None:
    store = MagicMock()
    store.available.return_value = True
    store.get_quotes.return_value = [
        QuoteRow(symbol="SHSE.600519", name="茅台", last_price=100.0, industry=""),
    ]
    db = MagicMock()
    with (
        patch.object(wl, "get_quote_store", return_value=store),
        patch.object(wl, "enrich_rows_from_db", side_effect=lambda _db, rows: (
            setattr(rows[0], "industry", "白酒") or 1
        )) as enrich_mock,
    ):
        out = wl._enrich([_item()], with_quotes=True, db=db)
    assert out[0].industry == "白酒"
    enrich_mock.assert_called_once()
    assert enrich_mock.call_args.args[0] is db


def test_enrich_keeps_redis_industry() -> None:
    store = MagicMock()
    store.available.return_value = True
    store.get_quotes.return_value = [
        QuoteRow(symbol="SHSE.600519", name="茅台", industry="已有行业"),
    ]

    def fake_enrich(_db, rows):
        assert rows[0].industry == "已有行业"
        return 0

    with (
        patch.object(wl, "get_quote_store", return_value=store),
        patch.object(wl, "enrich_rows_from_db", side_effect=fake_enrich),
    ):
        out = wl._enrich([_item()], with_quotes=True, db=MagicMock())
    assert out[0].industry == "已有行业"


def test_enrich_without_quotes_skips_industry() -> None:
    with patch.object(wl, "enrich_rows_from_db") as enrich_mock:
        out = wl._enrich([_item()], with_quotes=False, db=MagicMock())
    enrich_mock.assert_not_called()
    assert out[0].industry == ""
    assert out[0].last_price is None


def test_enrich_no_redis_still_looks_up_db() -> None:
    store = MagicMock()
    store.available.return_value = False

    def fill(_db, rows):
        assert len(rows) == 1
        assert rows[0].symbol == "SHSE.600519"
        rows[0].industry = "白酒"
        return 1

    with (
        patch.object(wl, "get_quote_store", return_value=store),
        patch.object(wl, "enrich_rows_from_db", side_effect=fill),
    ):
        out = wl._enrich([_item()], with_quotes=True, db=MagicMock())
    assert out[0].industry == "白酒"


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


def _api_client(*, db: MagicMock | None = None) -> TestClient:
    app = create_app()
    session = db if db is not None else MagicMock()

    def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: _make_user()
    return TestClient(app)


def test_quotes_endpoint_enriches_industry() -> None:
    store = MagicMock()
    store.available.return_value = True
    store.get_quotes.return_value = [
        QuoteRow(symbol="SHSE.600519", name="茅台", last_price=100.0, industry=""),
    ]

    def fill(_db, rows):
        rows[0].industry = "白酒"
        return 1

    with (
        patch.object(wl, "get_quote_store", return_value=store),
        patch.object(wl, "enrich_rows_from_db", side_effect=fill),
    ):
        client = _api_client()
        resp = client.get("/api/v1/quotes", params={"symbols": "600519.SSE"})
    assert resp.status_code == 200
    body = resp.json()
    assert body[0]["industry"] == "白酒"

from __future__ import annotations

from datetime import UTC, date, datetime
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.core.db import get_db
from app.core.security import hash_password
from app.main import create_app
from app.models.content import TradingPlan
from app.models.user import User
from app.schemas.market import RadarResonanceEntry, RadarResonanceOut
from app.services import plan_draft as pd


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


def test_clamp_top_n() -> None:
    assert pd.clamp_top_n(None) == 5
    assert pd.clamp_top_n(2) == 3
    assert pd.clamp_top_n(9) == 8
    assert pd.clamp_top_n(5) == 5


def test_normalize_trade_date() -> None:
    assert pd.normalize_trade_date("20260811") == "2026-08-11"
    assert pd.normalize_trade_date("2026-08-11") == "2026-08-11"
    assert pd.normalize_trade_date("bad") is None


def test_ice_stage_raises_no_write() -> None:
    db = MagicMock()
    with (
        patch("app.services.plan_draft.build_emotion_cycle", return_value={"stage": "ice", "stage_label": "冰点"}),
        patch("app.services.plan_draft.list_radar_cards") as cards,
    ):
        with pytest.raises(HTTPException) as ei:
            pd.create_resonance_plan_draft(db, "u1")
        assert ei.value.status_code == 400
        assert "不宜新开" in str(ei.value.detail)
        cards.assert_not_called()
        db.add.assert_not_called()
        db.commit.assert_not_called()


def test_recession_stage_raises_no_write() -> None:
    db = MagicMock()
    with (
        patch("app.services.plan_draft.build_emotion_cycle", return_value={"stage": "recession", "stage_label": "退潮"}),
        patch("app.services.plan_draft.list_radar_cards") as cards,
    ):
        with pytest.raises(HTTPException) as ei:
            pd.create_resonance_plan_draft(db, "u1")
        assert ei.value.status_code == 400
        assert "不宜新开" in str(ei.value.detail)
        cards.assert_not_called()
        db.add.assert_not_called()
        db.commit.assert_not_called()


def test_no_cards_400() -> None:
    db = MagicMock()
    with (
        patch("app.services.plan_draft.build_emotion_cycle", return_value={"stage": "divergence", "stage_label": "分歧"}),
        patch("app.services.plan_draft.list_radar_cards", return_value=[]),
    ):
        with pytest.raises(HTTPException) as ei:
            pd.create_resonance_plan_draft(db, "u1")
        assert ei.value.status_code == 400
        assert "雷达卡片" in str(ei.value.detail)


def test_empty_resonance_400() -> None:
    db = MagicMock()
    empty = RadarResonanceOut(min_cards=2, top_n=5, total=0, entries=[])
    with (
        patch("app.services.plan_draft.build_emotion_cycle", return_value={"stage": "divergence", "stage_label": "分歧"}),
        patch("app.services.plan_draft.list_radar_cards", return_value=[MagicMock()]),
        patch("app.services.plan_draft.list_radar_resonance", return_value=empty),
        patch("app.services.plan_draft.resolve_next_trade_date", return_value=("2026-08-11", False)),
    ):
        with pytest.raises(HTTPException) as ei:
            pd.create_resonance_plan_draft(db, "u1", top_n=5)
        assert "共振" in str(ei.value.detail)


def test_create_draft_and_replace() -> None:
    db = MagicMock()
    entries = [
        RadarResonanceEntry(
            vt_symbol="600519.SSE",
            name="茅台",
            card_count=2,
            card_titles=["选股·龙头", "发现·连板梯队"],
            resonance_score=2.9,
            change_pct=2.0,
            last_price=1800.0,
        )
    ]
    out = RadarResonanceOut(min_cards=2, top_n=5, total=1, entries=entries)

    # first call: no existing draft
    db.scalar.return_value = None
    db.scalars.return_value = []

    with (
        patch("app.services.plan_draft.build_emotion_cycle", return_value={"stage": "divergence", "stage_label": "分歧"}),
        patch("app.services.plan_draft.list_radar_cards", return_value=[MagicMock()]),
        patch("app.services.plan_draft.list_radar_resonance", return_value=out),
        patch("app.services.plan_draft.resolve_next_trade_date", return_value=("2026-08-11", False)),
        patch("app.services.plan_draft.uuid") as u,
    ):
        u.uuid4.return_value.hex = "abc123"
        result = pd.create_resonance_plan_draft(db, "u1", top_n=5)

    assert result["status"] == "draft"
    assert result["trade_date"] == "2026-08-11"
    assert result["replaced"] is False
    assert result["symbol_count"] == 1
    assert result["symbols"][0]["vt_symbol"] == "600519.SSE"
    assert result["emotion_expected"] == "divergence"
    assert db.add.called
    assert db.commit.called

    # second call: existing draft → replaced
    existing = MagicMock(spec=TradingPlan)
    existing.id = "oldplan"
    existing.status = "draft"
    db.scalar.return_value = existing
    db.reset_mock()

    with (
        patch("app.services.plan_draft.build_emotion_cycle", return_value={"stage": "divergence", "stage_label": "分歧"}),
        patch("app.services.plan_draft.list_radar_cards", return_value=[MagicMock()]),
        patch("app.services.plan_draft.list_radar_resonance", return_value=out),
        patch("app.services.plan_draft.resolve_next_trade_date", return_value=("2026-08-11", False)),
    ):
        result2 = pd.create_resonance_plan_draft(db, "u1", top_n=5)

    assert result2["replaced"] is True
    assert result2["plan_id"] == "oldplan"
    db.execute.assert_called()
    db.flush.assert_called()
    call_names = [c[0] for c in db.mock_calls]
    assert call_names.index("flush") < call_names.index("commit")
    db.delete.assert_not_called()


def test_replace_path_flush_before_commit() -> None:
    """Replace 路径：bulk delete 后 flush，再 insert symbols，最后 commit。"""
    db = MagicMock()
    existing = MagicMock(spec=TradingPlan)
    existing.id = "oldplan"
    db.scalar.return_value = existing

    entries = [
        RadarResonanceEntry(
            vt_symbol="600519.SSE",
            name="茅台",
            card_count=2,
            card_titles=["A"],
            resonance_score=1.0,
        )
    ]
    out = RadarResonanceOut(min_cards=2, top_n=5, total=1, entries=entries)

    with (
        patch("app.services.plan_draft.build_emotion_cycle", return_value={"stage": "divergence", "stage_label": "分歧"}),
        patch("app.services.plan_draft.list_radar_cards", return_value=[MagicMock()]),
        patch("app.services.plan_draft.list_radar_resonance", return_value=out),
        patch("app.services.plan_draft.resolve_next_trade_date", return_value=("2026-08-11", False)),
    ):
        result = pd.create_resonance_plan_draft(db, "u1", top_n=5)

    assert result["replaced"] is True
    db.execute.assert_called_once()
    db.flush.assert_called_once()
    call_names = [c[0] for c in db.mock_calls]
    assert call_names.index("execute") < call_names.index("flush") < call_names.index("commit")


def test_resolve_next_trade_date_calendar_hit() -> None:
    db = MagicMock()
    db.execute.return_value.scalar.return_value = "2026-08-12"
    td, fallback = pd.resolve_next_trade_date(db, today=date(2026, 8, 10))
    assert td == "2026-08-12"
    assert fallback is False
    db.execute.assert_called_once()


def test_resolve_next_trade_date_fallback() -> None:
    db = MagicMock()
    db.execute.return_value.scalar.return_value = None
    with patch("app.services.plan_draft.latest_open_yyyymmdd", return_value="20260811"):
        td, fallback = pd.resolve_next_trade_date(db, today=date(2026, 8, 10))
    assert td == "2026-08-11"
    assert fallback is True


def test_does_not_touch_active() -> None:
    """查 draft 的 where 必须含 status==draft；同日 active 计划不得 delete/update。"""
    db = MagicMock()
    active_plan = MagicMock(spec=TradingPlan)
    active_plan.id = "active-plan"
    active_plan.status = "active"
    active_plan.trade_date = "2026-08-11"

    # draft 查询未命中（scalar 只查 status==draft）；active 仍在「库中」但不应被触及
    db.scalar.return_value = None
    db.scalars.return_value = []

    entries = [
        RadarResonanceEntry(
            vt_symbol="600519.SSE",
            name="茅台",
            card_count=2,
            card_titles=["A"],
            resonance_score=1.0,
        )
    ]
    out = RadarResonanceOut(min_cards=2, top_n=5, total=1, entries=entries)
    with (
        patch("app.services.plan_draft.build_emotion_cycle", return_value={"stage": "startup", "stage_label": "启动"}),
        patch("app.services.plan_draft.list_radar_cards", return_value=[MagicMock()]),
        patch("app.services.plan_draft.list_radar_resonance", return_value=out),
        patch("app.services.plan_draft.resolve_next_trade_date", return_value=("2026-08-11", False)),
        patch("app.services.plan_draft.uuid") as u,
    ):
        u.uuid4.return_value.hex = "new1"
        pd.create_resonance_plan_draft(db, "u1")

    added = [c.args[0] for c in db.add.call_args_list if isinstance(c.args[0], TradingPlan)]
    assert added
    assert all(p.status == "draft" for p in added)
    assert all(p is not active_plan for p in added)

    deleted = [c.args[0] for c in db.delete.call_args_list]
    assert active_plan not in deleted

    db.scalar.assert_called_once()
    assert active_plan.emotion_expected != "startup"


def test_api_plan_draft_ok() -> None:
    user = _make_user()
    client = _api_client(user)
    payload = {
        "plan_id": "abc123",
        "trade_date": "2026-08-11",
        "status": "draft",
        "emotion_expected": "divergence",
        "symbol_count": 1,
        "symbols": [{"vt_symbol": "600519.SSE", "name": "茅台"}],
        "replaced": False,
    }
    with patch(
        "app.api.v1.market.plan_draft_svc.create_resonance_plan_draft",
        return_value=payload,
    ) as create:
        resp = client.post("/api/v1/radar/plan-draft", json={})
    assert resp.status_code == 200
    create.assert_called_once()
    assert create.call_args[0][1] == str(user.id)
    body = resp.json()
    assert body["plan_id"] == "abc123"
    assert body["trade_date"] == "2026-08-11"
    assert body["symbol_count"] == 1
    assert body["replaced"] is False


def test_api_plan_draft_bad_request() -> None:
    client = _api_client()
    with patch(
        "app.api.v1.market.plan_draft_svc.create_resonance_plan_draft",
        side_effect=HTTPException(status_code=400, detail="当前情绪不宜新开（冰点/退潮）"),
    ):
        resp = client.post("/api/v1/radar/plan-draft", json={})
    assert resp.status_code == 400
    assert "不宜新开" in resp.json()["detail"]


def test_append_creates_empty_draft_then_adds() -> None:
    db = MagicMock()
    db.scalar.return_value = None
    db.scalars.return_value = []
    with (
        patch.object(pd, "resolve_next_trade_date", return_value=("2026-08-17", False)),
        patch.object(pd, "uuid") as u,
    ):
        u.uuid4.return_value.hex = "newdraft"
        out = pd.append_symbol_to_draft(db, "u1", vt_symbol="600519.SSE", source="horizon")
    assert out["added"] is True
    assert out["trade_date"] == "2026-08-17"
    assert out["symbol_count"] == 1
    assert out["plan_id"] == "newdraft"
    assert "已加入" in out["message"]
    assert db.add.called
    assert db.flush.called
    assert db.commit.called


def test_append_idempotent_when_already_in_draft() -> None:
    db = MagicMock()
    plan = MagicMock(spec=TradingPlan)
    plan.id = "p1"
    plan.trade_date = "2026-08-17"
    db.scalar.return_value = plan
    sym = MagicMock()
    sym.symbol = "600519"
    sym.exchange = "SSE"
    db.scalars.return_value = [sym]
    with patch.object(pd, "resolve_next_trade_date", return_value=("2026-08-17", False)):
        out = pd.append_symbol_to_draft(db, "u1", vt_symbol="600519.SSE")
    assert out["added"] is False
    assert out["symbol_count"] == 1
    assert "已在" in out["message"]
    db.commit.assert_not_called()


def test_append_rejects_when_full() -> None:
    from app.services.plan_manage import MAX_PLAN_SYMBOLS

    db = MagicMock()
    plan = MagicMock(spec=TradingPlan)
    plan.id = "p1"
    db.scalar.return_value = plan
    fake = []
    for i in range(MAX_PLAN_SYMBOLS):
        s = MagicMock()
        s.symbol = f"{i:06d}"
        s.exchange = "SSE"
        fake.append(s)
    db.scalars.return_value = fake
    with patch.object(pd, "resolve_next_trade_date", return_value=("2026-08-17", False)):
        with pytest.raises(HTTPException) as ei:
            pd.append_symbol_to_draft(db, "u1", vt_symbol="600519.SSE")
    assert ei.value.status_code == 400
    assert "最多" in str(ei.value.detail)


def test_append_ice_stage_still_ok() -> None:
    db = MagicMock()
    db.scalar.return_value = None
    db.scalars.return_value = []
    with (
        patch.object(pd, "resolve_next_trade_date", return_value=("2026-08-17", False)),
        patch("app.services.plan_draft.build_emotion_cycle") as emo,
        patch.object(pd, "uuid") as u,
    ):
        u.uuid4.return_value.hex = "iceok"
        out = pd.append_symbol_to_draft(db, "u1", vt_symbol="600519.SSE")
    assert out["added"] is True
    emo.assert_not_called()


def test_api_draft_append() -> None:
    user = _make_user()
    client = _api_client(user)
    with patch(
        "app.api.v1.content.plan_draft_svc.append_symbol_to_draft",
        return_value={
            "added": True,
            "plan_id": "p1",
            "trade_date": "2026-08-17",
            "symbol_count": 1,
            "status": "draft",
            "message": "已加入草案 600519.SSE",
        },
    ) as append:
        resp = client.post(
            "/api/v1/playbook/plans/draft-append",
            json={"vt_symbol": "600519.SSE", "source": "horizon"},
        )
    assert resp.status_code == 200
    append.assert_called_once()
    assert append.call_args[0][1] == str(user.id)
    body = resp.json()
    assert body["added"] is True
    assert body["plan_id"] == "p1"

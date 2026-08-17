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
from app.models.content import TradingPlan
from app.models.user import User
from app.schemas.content import PlanOut
from app.services import feed as feed_svc
from app.services import plan_manage as pm


def test_plan_to_out_maps_symbols() -> None:
    plan = MagicMock()
    plan.id = "p1"
    plan.trade_date = "2026-08-14"
    plan.emotion_expected = "divergence"
    plan.max_position_pct = 0.3
    plan.notes = "n"
    plan.status = "draft"
    sym = MagicMock()
    sym.symbol = "600519"
    sym.exchange = "SSE"
    sym.allowed_modes = ""
    sym.entry_conditions = "e"
    sym.exit_conditions = ""
    out = feed_svc.plan_to_out(plan, [sym])
    assert isinstance(out, PlanOut)
    assert out.id == "p1"
    assert out.status == "draft"
    assert out.symbols[0]["vt_symbol"] == "600519.SSE"


def _plan(**kw):
    p = MagicMock(spec=TradingPlan)
    p.id = kw.get("id", "p1")
    p.user_id = kw.get("user_id", "u1")
    p.trade_date = kw.get("trade_date", "2026-08-14")
    p.status = kw.get("status", "draft")
    p.emotion_expected = ""
    p.max_position_pct = 0.3
    p.notes = ""
    p.updated_at = "t0"
    return p


def test_activate_replaces_same_day_active() -> None:
    draft = _plan(id="d1", status="draft")
    old = _plan(id="a1", status="active")
    db = MagicMock()
    # get_user_plan → draft；再查同日 active → [old]
    db.scalar.side_effect = [draft]
    db.scalars.return_value = iter([old])
    with (
        patch("app.services.plan_manage._now", return_value="t1"),
        patch("app.services.plan_manage.load_plan_out", return_value=MagicMock(status="active", id="d1")),
    ):
        out = pm.activate_plan(db, "u1", "d1")
    assert old.status == "abandoned"
    assert draft.status == "active"
    assert draft.updated_at == "t1"
    db.commit.assert_called()
    assert out.id == "d1"


def test_abandon_idempotent() -> None:
    abandoned = _plan(status="abandoned")
    db = MagicMock()
    db.scalar.return_value = abandoned
    with patch(
        "app.services.plan_manage.load_plan_out",
        return_value=MagicMock(status="abandoned", id="p1"),
    ):
        out = pm.abandon_plan(db, "u1", "p1")
    assert abandoned.status == "abandoned"
    db.commit.assert_not_called()
    assert out.status == "abandoned"


def test_activate_missing_404() -> None:
    db = MagicMock()
    db.scalar.return_value = None
    with pytest.raises(HTTPException) as ei:
        pm.activate_plan(db, "u1", "missing")
    assert ei.value.status_code == 404


def test_update_rejects_abandoned() -> None:
    plan = _plan(status="abandoned")
    db = MagicMock()
    db.scalar.return_value = plan
    with pytest.raises(HTTPException) as ei:
        pm.update_plan(db, "u1", "p1", notes="x")
    assert ei.value.status_code == 403


def test_update_symbols_replace() -> None:
    plan = _plan(status="draft")
    db = MagicMock()
    db.scalar.return_value = plan
    db.scalars.return_value = iter([])
    with (
        patch("app.services.plan_manage._now", return_value="t2"),
        patch(
            "app.services.plan_manage.load_plan_out",
            return_value=MagicMock(id="p1", notes="hi"),
        ),
    ):
        pm.update_plan(db, "u1", "p1", notes="hi", symbols=["600519.SSE", "000001.SZSE"])
    assert plan.notes == "hi"
    db.execute.assert_called()  # delete symbols
    assert db.add.call_count == 2
    db.commit.assert_called()


def test_update_max_pct_percent_form() -> None:
    plan = _plan(status="active")
    db = MagicMock()
    db.scalar.return_value = plan
    with patch(
        "app.services.plan_manage.load_plan_out",
        return_value=MagicMock(id="p1"),
    ):
        pm.update_plan(db, "u1", "p1", max_position_pct=30)
    assert abs(plan.max_position_pct - 0.3) < 1e-9


def test_update_rejects_all_none() -> None:
    plan = _plan(status="draft")
    db = MagicMock()
    db.scalar.return_value = plan
    with pytest.raises(HTTPException) as ei:
        pm.update_plan(db, "u1", "p1")
    assert ei.value.status_code == 400


def test_update_symbols_empty_clears() -> None:
    plan = _plan(status="draft")
    db = MagicMock()
    db.scalar.return_value = plan
    db.scalars.return_value = iter([])
    with (
        patch("app.services.plan_manage._now", return_value="t2"),
        patch(
            "app.services.plan_manage.load_plan_out",
            return_value=MagicMock(id="p1"),
        ),
    ):
        pm.update_plan(db, "u1", "p1", symbols=[])
    db.execute.assert_called()
    assert db.add.call_count == 0
    db.commit.assert_called()


def test_replace_symbols_preserves_entry_conditions() -> None:
    """同 vt 重建时保留 allowed_modes / entry_conditions / exit_conditions；新 vt 为空串。"""
    plan = _plan(status="draft")
    existing = MagicMock()
    existing.symbol = "600519"
    existing.exchange = "SSE"
    existing.allowed_modes = "swing"
    existing.entry_conditions = "雷达共振文案"
    existing.exit_conditions = "止损"
    db = MagicMock()
    db.scalar.return_value = plan
    db.scalars.return_value = iter([existing])
    with (
        patch("app.services.plan_manage._now", return_value="t2"),
        patch(
            "app.services.plan_manage.load_plan_out",
            return_value=MagicMock(id="p1"),
        ),
    ):
        pm.update_plan(db, "u1", "p1", symbols=["600519.SSE", "000001.SZSE"])
    assert db.add.call_count == 2
    kept = db.add.call_args_list[0].args[0]
    assert kept.symbol == "600519"
    assert kept.allowed_modes == "swing"
    assert kept.entry_conditions == "雷达共振文案"
    assert kept.exit_conditions == "止损"
    brand_new = db.add.call_args_list[1].args[0]
    assert brand_new.symbol == "000001"
    assert brand_new.allowed_modes == ""
    assert brand_new.entry_conditions == ""
    assert brand_new.exit_conditions == ""


def test_activate_then_off_plan_uses_plan_symbols() -> None:
    """activate 后 status=active；snapshot 的 vt 集合可正确驱动 list_off_plan_vt_symbols。"""
    from app.services import off_plan as op

    draft = _plan(id="d1", status="draft", trade_date="2026-08-14")
    db_act = MagicMock()
    db_act.scalar.side_effect = [draft]
    db_act.scalars.return_value = iter([])
    with (
        patch("app.services.plan_manage._now", return_value="t1"),
        patch(
            "app.services.plan_manage.load_plan_out",
            return_value=MagicMock(status="active", id="d1"),
        ),
    ):
        out = pm.activate_plan(db_act, "u1", "d1")
    assert draft.status == "active"
    assert out.status == "active"
    db_act.commit.assert_called()

    sym = MagicMock()
    sym.symbol = "600519"
    sym.exchange = "SSE"
    db_snap = MagicMock()
    db_snap.scalar.return_value = draft
    db_snap.scalars.return_value = iter([sym])
    snap = op.load_active_plan_snapshot(db_snap, "u1", "2026-08-14")
    assert snap is not None
    assert snap["vt_symbols"] == {"600519.SSE"}
    assert op.list_off_plan_vt_symbols(["600519.SSE", "000001.SZSE"], snap["vt_symbols"]) == ["000001.SZSE"]
    assert op.list_off_plan_vt_symbols(["600519.SSE", "000001.SZSE"], None) == []


def test_update_notes_only_skips_symbols() -> None:
    plan = _plan(status="draft")
    db = MagicMock()
    db.scalar.return_value = plan
    with (
        patch("app.services.plan_manage._now", return_value="t2"),
        patch(
            "app.services.plan_manage.load_plan_out",
            return_value=MagicMock(id="p1", notes="x"),
        ),
    ):
        pm.update_plan(db, "u1", "p1", notes="x")
    assert plan.notes == "x"
    db.execute.assert_not_called()
    db.add.assert_not_called()
    db.commit.assert_called()


def test_update_rejects_too_many_symbols() -> None:
    plan = _plan(status="draft")
    db = MagicMock()
    db.scalar.return_value = plan
    symbols = [f"{600500 + i}.SSE" for i in range(21)]
    with pytest.raises(HTTPException) as ei:
        pm.update_plan(db, "u1", "p1", symbols=symbols)
    assert ei.value.status_code == 400


@pytest.mark.parametrize(
    "symbols",
    [
        [""],
        ["600519.SSE", "   "],
    ],
)
def test_update_rejects_empty_symbol(symbols: list[str]) -> None:
    plan = _plan(status="draft")
    db = MagicMock()
    db.scalar.return_value = plan
    with pytest.raises(HTTPException) as ei:
        pm.update_plan(db, "u1", "p1", symbols=symbols)
    assert ei.value.status_code == 400


def test_update_rejects_invalid_symbol() -> None:
    plan = _plan(status="draft")
    db = MagicMock()
    db.scalar.return_value = plan
    with (
        patch(
            "app.services.plan_manage.parse_flexible_symbol",
            side_effect=ValueError("无效 vt_symbol：bogus"),
        ),
        pytest.raises(HTTPException) as ei,
    ):
        pm.update_plan(db, "u1", "p1", symbols=["bogus"])
    assert ei.value.status_code == 400


@pytest.mark.parametrize("max_position_pct", [0, -1, 0.0])
def test_update_rejects_non_positive_max_pct(max_position_pct: float) -> None:
    plan = _plan(status="draft")
    db = MagicMock()
    db.scalar.return_value = plan
    with pytest.raises(HTTPException) as ei:
        pm.update_plan(db, "u1", "p1", max_position_pct=max_position_pct)
    assert ei.value.status_code == 400


def _user() -> User:
    now = datetime.now(UTC)
    return User(
        id=str(uuid4()),
        username="demo",
        display_name="Demo",
        password_hash=hash_password("x"),
        is_active=True,
        created_at=now,
        updated_at=now,
    )


def _client() -> tuple[TestClient, User]:
    app = create_app()
    u = _user()

    def override_db():
        yield MagicMock()

    def override_user():
        return u

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user
    return TestClient(app), u


def test_api_activate_ok() -> None:
    client, u = _client()
    fake = PlanOut(
        id="p1",
        trade_date="2026-08-14",
        emotion_expected="",
        max_position_pct=0.3,
        notes="",
        status="active",
        symbols=[],
    )
    with patch("app.api.v1.content.plan_manage_svc.activate_plan", return_value=fake) as act:
        r = client.post("/api/v1/playbook/plans/p1/activate")
    assert r.status_code == 200
    assert r.json()["data"]["status"] == "active"
    act.assert_called_once()
    assert act.call_args.args[1] == str(u.id)


def test_api_patch_ok() -> None:
    client, u = _client()
    fake = PlanOut(
        id="p1",
        trade_date="2026-08-14",
        emotion_expected="",
        max_position_pct=0.25,
        notes="x",
        status="draft",
        symbols=[],
    )
    with patch("app.api.v1.content.plan_manage_svc.update_plan", return_value=fake) as upd:
        r = client.patch("/api/v1/playbook/plans/p1", json={"notes": "x", "max_position_pct": 0.25})
    assert r.status_code == 200
    assert r.json()["data"]["notes"] == "x"
    upd.assert_called_once()

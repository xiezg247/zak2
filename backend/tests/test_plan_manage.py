from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.models.content import TradingPlan
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
        patch("app.services.plan_manage.load_plan_out", return_value=MagicMock(status="active", id="d1")) as load,
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

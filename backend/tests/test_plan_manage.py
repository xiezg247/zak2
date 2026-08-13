from __future__ import annotations

from unittest.mock import MagicMock

from app.schemas.content import PlanOut
from app.services import feed as feed_svc


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

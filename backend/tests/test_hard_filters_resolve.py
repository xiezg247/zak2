from __future__ import annotations

from app.schemas.screener import HardFilterPrefs
from app.services.hard_filters import resolve_hard_filter


def test_resolve_template_only() -> None:
    p = resolve_hard_filter(None, "conservative")
    assert p.min_amount_wan == 5000.0
    assert p.allowed_industries == ""


def test_resolve_merge_industries_keep_template_amounts() -> None:
    overlay = HardFilterPrefs.model_validate({"allowed_industries": "白酒,银行"})
    assert overlay.model_fields_set == {"allowed_industries"}
    p = resolve_hard_filter(overlay, "conservative")
    assert p.allowed_industries == "白酒,银行"
    assert p.min_amount_wan == 5000.0
    assert p.min_total_mv_yi == 100.0


def test_resolve_prefs_only() -> None:
    p = resolve_hard_filter(HardFilterPrefs(min_amount_wan=1, allowed_industries="x"), None)
    assert p.min_amount_wan == 1
    assert p.allowed_industries == "x"


def test_resolve_both_none_returns_balanced() -> None:
    p = resolve_hard_filter(None, None)
    assert p.min_amount_wan == 3000.0
    assert p.min_total_mv_yi == 50.0

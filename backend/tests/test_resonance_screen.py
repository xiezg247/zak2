from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from app.core.errors import ValidationFailed

from app.schemas.market import RadarResonanceEntry, RadarResonanceOut
from app.schemas.screener import HardFilterPrefs, RecipeRunRequest
from app.services.screener.engine import run_recipe_screen
from app.services.screener.presets import get_builtin_recipe


def test_radar_resonance_recipe_registered() -> None:
    recipe = get_builtin_recipe("radar_resonance")
    assert recipe is not None
    assert recipe.implemented is True
    assert recipe.name == "雷达共振"
    assert recipe.top_n == 20


def test_run_resonance_no_cards_raises_400() -> None:
    db = MagicMock()
    with patch(
        "app.domains.screener.resonance_screen.list_radar_cards",
        return_value=[],
    ):
        from app.services.screener.resonance_screen import run_resonance_screen

        with pytest.raises(ValidationFailed) as ei:
            run_resonance_screen(
                db=db,
                user_id="u1",
                top_n=20,
                hard_filter=HardFilterPrefs(min_amount_wan=0, min_total_mv_yi=0),
            )
        assert ei.value.status_code == 400
        assert "雷达卡片" in str(ei.value.detail)


def test_run_resonance_with_entries() -> None:
    db = MagicMock()
    entries = [
        RadarResonanceEntry(
            vt_symbol="600519.SSE",
            name="茅台",
            card_count=3,
            card_titles=["选股·龙头", "发现·连板梯队"],
            resonance_score=2.9,
            change_pct=2.0,
            last_price=1800.0,
            seal_time_label="09:30 封板",
        )
    ]
    out = RadarResonanceOut(min_cards=2, top_n=20, total=1, entries=entries)
    with (
        patch("app.domains.screener.resonance_screen.list_radar_cards", return_value=[MagicMock()]),
        patch("app.domains.screener.resonance_screen.list_radar_resonance", return_value=out) as lr,
    ):
        from app.services.screener.resonance_screen import run_resonance_screen

        result = run_resonance_screen(
            db=db,
            user_id="u1",
            top_n=12,
            hard_filter=HardFilterPrefs(min_amount_wan=0, min_total_mv_yi=0),
        )
    lr.assert_called_once()
    assert lr.call_args.kwargs["user_id"] == "u1"
    assert lr.call_args.kwargs["top_n"] == 12
    assert lr.call_args.kwargs["min_cards"] == 2
    assert result["source"] == "radar_resonance"
    assert result["row_count"] == 1
    assert "雷达共振" in result["condition"]
    row = result["rows"][0]
    assert row["vt_symbol"] == "600519.SSE"
    assert row["score"] == 2.9
    assert "共振" in row["hit_reason"]
    assert "选股·龙头" in row["hit_reason"]
    assert row.get("seal_time_label") == "09:30 封板"
    assert result["config"]["recipe_id"] == "radar_resonance"
    assert result["config"]["min_cards"] == 2


def test_run_resonance_empty_entries_ok() -> None:
    db = MagicMock()
    out = RadarResonanceOut(min_cards=2, top_n=20, total=0, entries=[])
    with (
        patch("app.domains.screener.resonance_screen.list_radar_cards", return_value=[MagicMock()]),
        patch("app.domains.screener.resonance_screen.list_radar_resonance", return_value=out),
    ):
        from app.services.screener.resonance_screen import run_resonance_screen

        result = run_resonance_screen(
            db=db,
            user_id="u1",
            top_n=20,
            hard_filter=HardFilterPrefs(min_amount_wan=0, min_total_mv_yi=0),
        )
    assert result["source"] == "radar_resonance"
    assert result["row_count"] == 0
    assert "暂无共振" in result["condition"]


def test_run_recipe_screen_radar_resonance_branch() -> None:
    fake = {
        "condition": "雷达共振",
        "source": "radar_resonance",
        "row_count": 0,
        "total_scanned": 0,
        "config": {},
        "rows": [],
        "industry_dist": [],
        "diff": None,
    }
    with patch("app.domains.screener.resonance_screen.run_resonance_screen", return_value=fake) as run:
        result = run_recipe_screen(
            RecipeRunRequest(
                recipe_id="radar_resonance",
                top_n=20,
                hard_filter=HardFilterPrefs(min_amount_wan=0, min_total_mv_yi=0),
            ),
            db=MagicMock(),
            user_id="u1",
        )
    assert result["source"] == "radar_resonance"
    run.assert_called_once()
    assert run.call_args.kwargs["user_id"] == "u1"


def test_run_recipe_screen_resonance_requires_user() -> None:
    with pytest.raises(ValidationFailed) as ei:
        run_recipe_screen(
            RecipeRunRequest(
                recipe_id="radar_resonance",
                hard_filter=HardFilterPrefs(min_amount_wan=0, min_total_mv_yi=0),
            ),
            db=MagicMock(),
            user_id=None,
        )
    assert ei.value.status_code == 400

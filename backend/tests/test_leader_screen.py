from __future__ import annotations

from app.domains.screener.schemas import HardFilterPrefs, RecipeRunRequest
from app.domains.market.quotes import QuoteRow
from app.domains.screener.engine import run_recipe_screen
from app.domains.screener.leader_screen import (
    _write_seal_time_fields,
    compute_leader_score,
    infer_emotion_stage,
    rank_leader_pool,
)
from app.domains.screener.presets import get_builtin_recipe


def _row(symbol: str, **kwargs) -> QuoteRow:
    base = {
        "symbol": symbol,
        "name": "测试",
        "change_pct": 9.8,
        "turnover_rate": 8.0,
        "amount": 2e8,
        "volume": 1e6,
        "volume_ratio": 2.0,
        "limit_times": 2,
        "industry": "半导体",
        "net_mf_amount": 3000,
    }
    base.update(kwargs)
    return QuoteRow(**base)  # type: ignore[arg-type]


def test_radar_leader_recipe_registered() -> None:
    recipe = get_builtin_recipe("radar_leader")
    assert recipe is not None
    assert recipe.implemented is True
    assert recipe.top_n == 12


def test_infer_emotion_stage() -> None:
    assert infer_emotion_stage({"max_limit_times": 0}) == "ice"
    assert infer_emotion_stage({"max_limit_times": 1}) == "startup"
    assert infer_emotion_stage({"max_limit_times": 3}) == "divergence"
    assert infer_emotion_stage({"max_limit_times": 6}) == "climax"


def test_rank_leader_pool_assigns_tiers() -> None:
    rows = [
        _row("SHSE.A", name="龙一", limit_times=4, amount=5e8, industry="芯片"),
        _row("SHSE.B", name="龙二", limit_times=3, amount=3e8, industry="芯片"),
        _row("SHSE.C", name="跟风", limit_times=2, amount=1e8, industry="芯片"),
        _row("SZSE.D", name="异军", limit_times=5, amount=6e8, industry="新能源"),
    ]
    ranked = rank_leader_pool(rows, top_n=4, variant="mainline")
    assert len(ranked) >= 3
    assert ranked[0].__dict__["_leader_tier"] == "dragon_1"
    assert any(r.__dict__.get("_leader_tier") == "dragon_2" for r in ranked)


def test_compute_leader_score_range() -> None:
    row = _row("SHSE.X", limit_times=3, amount=4e8, net_mf_amount=8000)
    score = compute_leader_score(row, amount_rank=0.9, sector_strength=1.0, max_net_mf=10000)
    assert 20 <= score <= 100


def test_seal_time_raises_leader_score() -> None:
    row = _row("SHSE.600519", limit_times=3, amount=4e8, net_mf_amount=8000)
    base = compute_leader_score(row, amount_rank=0.9, sector_strength=1.0, max_net_mf=10000)
    with_seal = compute_leader_score(row, amount_rank=0.9, sector_strength=1.0, max_net_mf=10000, seal_time=1.0)
    assert with_seal > base

    row_no = _row("SHSE.600519", limit_times=3, amount=4e8, net_mf_amount=8000)
    row_yes = _row("SHSE.600519", limit_times=3, amount=4e8, net_mf_amount=8000)
    ranked_no = rank_leader_pool([row_no], top_n=1, first_time_map={})
    ranked_yes = rank_leader_pool([row_yes], top_n=1, first_time_map={"SHSE.600519": "0930"})
    assert ranked_yes[0].__dict__["_score"] > ranked_no[0].__dict__["_score"]
    assert ranked_yes[0].__dict__["_first_time"] == "0930"
    assert ranked_yes[0].__dict__["_seal_time_score"] == 1.0
    assert "09:30 封板" in ranked_yes[0].__dict__["_hit_reason"]


def test_write_seal_time_fields_ignores_desktop_vt_symbol() -> None:
    """打包/API 行带桌面 vt_symbol 时，仍按 TickFlow symbol 命中 first_time_map。"""
    rows = [
        {
            "vt_symbol": "600519.SSE",
            "symbol": "SHSE.600519",
            "name": "茅台",
        }
    ]
    _write_seal_time_fields(rows, {"SHSE.600519": "0930"})
    assert rows[0]["first_time"] == "0930"
    assert rows[0]["seal_time_score"] == 1.0
    assert rows[0]["seal_time_label"] == "09:30 封板"
    assert rows[0]["tf_symbol"] == "SHSE.600519"


def test_run_radar_leader_recipe() -> None:
    class _Store:
        def available(self) -> bool:
            return True

        def meta(self) -> dict:
            return {"quote_count": 4, "available": True}

        def load_ranked_quotes(self, field: str, *, pool: int = 500) -> list[QuoteRow]:
            _ = field, pool
            return [
                _row("SHSE.A", name="甲", limit_times=3, industry="芯片", amount=4e8),
                _row("SHSE.B", name="乙", limit_times=2, industry="芯片", amount=2e8),
                _row("SZSE.C", name="丙", limit_times=1, industry="白酒", amount=3e8, change_pct=10.0),
                _row("SZSE.D", name="丁", limit_times=0, industry="银行", change_pct=1.0, amount=1e7),
            ]

    result = run_recipe_screen(
        RecipeRunRequest(
            recipe_id="radar_leader",
            top_n=5,
            variant="mainline",
            hard_filter=HardFilterPrefs(min_amount_wan=0, min_total_mv_yi=0),
        ),
        store=_Store(),  # type: ignore[arg-type]
        db=None,
    )
    assert result["source"] == "radar_leader"
    assert result["row_count"] >= 1
    assert "雷达龙头" in result["condition"]
    assert result["rows"][0].get("leader_tier") in {"dragon_1", "dragon_2", "follower"}


def test_radar_leader_enriches_empty_industry_before_filter() -> None:
    from unittest.mock import MagicMock, patch

    class _Store:
        def available(self) -> bool:
            return True

        def meta(self) -> dict:
            return {"quote_count": 1, "available": True}

        def load_ranked_quotes(self, field: str, *, pool: int = 500) -> list[QuoteRow]:
            _ = field, pool
            return [
                _row("SHSE.600519", name="茅台", limit_times=3, industry="", amount=4e8),
            ]

    with (
        patch(
            "app.domains.market.stock_industry.load_industry_map",
            return_value={"SHSE.600519": "白酒"},
        ),
        patch(
            "app.domains.screener.leader_screen.resolve_emotion_stage",
            return_value=("startup", {"stage": "startup", "stage_label": "启动"}),
        ),
        patch("app.domains.screener.leader_screen.market_svc.load_emotion", return_value=None),
        patch("app.domains.screener.leader_screen.load_first_time_map", return_value={}),
    ):
        result = run_recipe_screen(
            RecipeRunRequest(
                recipe_id="radar_leader",
                top_n=5,
                variant="mainline",
                hard_filter=HardFilterPrefs(
                    min_amount_wan=0,
                    min_total_mv_yi=0,
                    allowed_industries="白酒",
                ),
            ),
            store=_Store(),  # type: ignore[arg-type]
            db=MagicMock(),
        )
    assert result["row_count"] >= 1
    assert result["rows"][0]["industry"] == "白酒"

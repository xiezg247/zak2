from __future__ import annotations

from app.schemas.market import RadarCardOut
from app.services.radar_resonance import CARD_WEIGHTS, compute_resonance


def test_compute_resonance_min_cards() -> None:
    cards = [
        RadarCardOut(
            card_id="leader_pick",
            title="选股·龙头",
            source="test",
            rows=[
                {"vt_symbol": "600519.SSE", "name": "茅台", "change_pct": 2.0},
                {"vt_symbol": "000001.SZSE", "name": "平安"},
            ],
        ),
        RadarCardOut(
            card_id="discovery_limit_ladder",
            title="发现·连板梯队",
            source="test",
            rows=[
                {"vt_symbol": "600519.SSE", "name": "茅台", "limit_times": 2},
                {"vt_symbol": "600000.SSE", "name": "浦发"},
            ],
        ),
        RadarCardOut(
            card_id="discovery_change_top",
            title="发现·涨幅榜",
            source="test",
            rows=[{"tf_symbol": "SHSE.600519", "name": "茅台", "change_pct": 2.1}],
        ),
    ]
    out = compute_resonance(cards, min_cards=2, top_n=10)
    assert out.total >= 1
    top = out.entries[0]
    assert top.vt_symbol == "600519.SSE"
    assert top.card_count == 3
    assert top.resonance_score == round(1.5 + 1.4 + 1.0, 2)
    assert "选股·龙头" in top.card_titles
    assert CARD_WEIGHTS["leader_pick"] == 1.5
    assert CARD_WEIGHTS["discovery_limit_ladder"] == 1.4


def test_compute_resonance_skips_sector() -> None:
    cards = [
        RadarCardOut(
            card_id="sector_flow_hot",
            title="板块·资金热力",
            source="test",
            rows=[{"sector_id": "xx", "name": "概念"}],
        ),
        RadarCardOut(
            card_id="leader_pick",
            title="选股·龙头",
            source="test",
            rows=[{"vt_symbol": "600519.SSE", "name": "茅台"}],
        ),
    ]
    out = compute_resonance(cards, min_cards=1, top_n=10)
    assert out.total == 1
    assert out.entries[0].vt_symbol == "600519.SSE"


def test_compute_resonance_seal_time_label_from_map() -> None:
    cards = [
        RadarCardOut(
            card_id="leader_pick",
            title="选股·龙头",
            source="test",
            rows=[{"vt_symbol": "600519.SSE", "name": "茅台"}],
        ),
        RadarCardOut(
            card_id="discovery_limit_ladder",
            title="发现·连板梯队",
            source="test",
            rows=[{"vt_symbol": "600519.SSE", "name": "茅台"}],
        ),
    ]
    out = compute_resonance(
        cards,
        min_cards=2,
        top_n=10,
        first_time_map={"SHSE.600519": "0935"},
    )
    assert out.total == 1
    assert out.entries[0].seal_time_label == "09:35 封板"
    # 权重未因 seal 改变
    assert out.entries[0].resonance_score == round(1.5 + 1.4, 2)


def test_compute_resonance_seal_time_label_from_row() -> None:
    cards = [
        RadarCardOut(
            card_id="leader_pick",
            title="选股·龙头",
            source="test",
            rows=[
                {
                    "vt_symbol": "600519.SSE",
                    "name": "茅台",
                    "seal_time_label": "09:30 封板",
                }
            ],
        ),
        RadarCardOut(
            card_id="discovery_limit_ladder",
            title="发现·连板梯队",
            source="test",
            rows=[{"vt_symbol": "600519.SSE", "name": "茅台"}],
        ),
    ]
    out = compute_resonance(cards, min_cards=2, top_n=10)
    assert out.entries[0].seal_time_label == "09:30 封板"

from __future__ import annotations

from app.services.emotion_cycle import DEFAULT_THRESHOLDS, estimate_fear_greed_proxy
from app.services.emotion_hysteresis import apply_stage_hysteresis, reset_emotion_stage_hysteresis


def test_hysteresis_holds_startup_near_threshold() -> None:
    reset_emotion_stage_hysteresis()
    t = DEFAULT_THRESHOLDS
    # 先进入启动
    assert (
        apply_stage_hysteresis(
            "startup",
            {"limit_up_count": 55, "max_limit_times": 3, "limit_ladder_depth": 1},
            t,
        )
        == "startup"
    )
    # 涨停回落到 48（仍 >= 50-5），应维持启动而非切到默认分歧
    held = apply_stage_hysteresis(
        "divergence",
        {"limit_up_count": 48, "max_limit_times": 2, "limit_ladder_depth": 0},
        t,
    )
    assert held == "startup"
    reset_emotion_stage_hysteresis()


def test_hysteresis_immediate_recession() -> None:
    reset_emotion_stage_hysteresis()
    t = DEFAULT_THRESHOLDS
    apply_stage_hysteresis(
        "startup",
        {"limit_up_count": 55, "max_limit_times": 3, "limit_ladder_depth": 1},
        t,
    )
    assert (
        apply_stage_hysteresis(
            "recession",
            {"limit_up_count": 10, "max_limit_times": 1, "limit_ladder_depth": 0},
            t,
        )
        == "recession"
    )
    reset_emotion_stage_hysteresis()


def test_fear_greed_proxy_range() -> None:
    low = estimate_fear_greed_proxy(up_ratio=0.2, limit_up_count=5, limit_down_count=40)
    high = estimate_fear_greed_proxy(up_ratio=0.8, limit_up_count=90, limit_down_count=5)
    assert 0 <= low <= 100
    assert 0 <= high <= 100
    assert high > low

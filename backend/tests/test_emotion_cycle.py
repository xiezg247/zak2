from __future__ import annotations

from app.services.emotion_cycle import classify_stage


def test_classify_recession_by_limit_down() -> None:
    assert (
        classify_stage(
            limit_up_count=40,
            limit_down_count=25,
            up_ratio=0.4,
            max_limit_times=4,
            limit_ladder_depth=2,
        )
        == "recession"
    )


def test_classify_ice() -> None:
    assert (
        classify_stage(
            limit_up_count=10,
            limit_down_count=16,
            up_ratio=0.3,
            max_limit_times=2,
            limit_ladder_depth=0,
        )
        == "ice"
    )


def test_classify_climax() -> None:
    assert (
        classify_stage(
            limit_up_count=90,
            limit_down_count=5,
            up_ratio=0.7,
            max_limit_times=6,
            limit_ladder_depth=3,
        )
        == "climax"
    )


def test_classify_divergence_default() -> None:
    """未命中其它阶段时默认分歧。"""
    assert (
        classify_stage(
            limit_up_count=20,
            limit_down_count=5,
            up_ratio=0.55,
            max_limit_times=1,
            limit_ladder_depth=0,
        )
        == "divergence"
    )


def test_classify_divergence_with_relaxed_recession() -> None:
    """自定义阈值下可走显式分歧分支。"""
    from app.services.emotion_cycle import Thresholds

    t = Thresholds(recession_limit_down=40)
    assert (
        classify_stage(
            limit_up_count=35,
            limit_down_count=30,
            up_ratio=0.5,
            max_limit_times=3,
            limit_ladder_depth=1,
            thresholds=t,
        )
        == "divergence"
    )


def test_classify_startup() -> None:
    assert (
        classify_stage(
            limit_up_count=55,
            limit_down_count=5,
            up_ratio=0.65,
            max_limit_times=3,
            limit_ladder_depth=1,
        )
        == "startup"
    )


def test_classify_prev_leader_limit_down_forces_recession() -> None:
    assert (
        classify_stage(
            limit_up_count=80,
            limit_down_count=5,
            up_ratio=0.7,
            max_limit_times=5,
            limit_ladder_depth=3,
            prev_leader_limit_down=True,
        )
        == "recession"
    )

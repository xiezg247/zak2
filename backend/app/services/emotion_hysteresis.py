"""情绪阶段 hysteresis：避免阈值边界附近抖动。"""

from __future__ import annotations

from typing import Any

# 维持当前阶段的放宽量（相对进入阈值）
_HOLD_STARTUP_LIMIT_UP_DELTA = 5
_HOLD_CLIMAX_LIMIT_UP_DELTA = 10
_HOLD_CLIMAX_LADDER_DELTA = 1
_HOLD_DIVERGENCE_LIMIT_UP_DELTA = 5

_STABLE_STAGE: str | None = None


def reset_emotion_stage_hysteresis() -> None:
    global _STABLE_STAGE
    _STABLE_STAGE = None


def _hold_stage(stage: str, inputs: dict[str, Any], thresholds: Any) -> bool:
    limit_up = int(inputs.get("limit_up_count") or 0)
    max_boards = int(inputs.get("max_limit_times") or 0)
    ladder = int(inputs.get("limit_ladder_depth") or 0)

    if stage == "startup":
        return bool(
            limit_up >= thresholds.startup_limit_up - _HOLD_STARTUP_LIMIT_UP_DELTA
            or max_boards >= thresholds.startup_max_boards
        )
    if stage == "climax":
        return bool(
            limit_up >= thresholds.climax_limit_up - _HOLD_CLIMAX_LIMIT_UP_DELTA
            and ladder >= max(0, thresholds.climax_ladder_depth - _HOLD_CLIMAX_LADDER_DELTA)
        )
    if stage == "divergence":
        return bool(limit_up >= thresholds.divergence_limit_up_min - _HOLD_DIVERGENCE_LIMIT_UP_DELTA)
    return False


def apply_stage_hysteresis(
    raw_stage: str,
    inputs: dict[str, Any],
    thresholds: Any,
    *,
    enabled: bool = True,
) -> str:
    """在 raw 判定与上一稳定阶段之间做迟滞；退潮/冰点立即切换。"""
    global _STABLE_STAGE

    if not enabled:
        _STABLE_STAGE = raw_stage
        return raw_stage

    stable = _STABLE_STAGE
    if stable is None or raw_stage == stable:
        _STABLE_STAGE = raw_stage
        return raw_stage

    if raw_stage in {"recession", "ice"}:
        _STABLE_STAGE = raw_stage
        return raw_stage

    if stable in {"recession", "ice"}:
        _STABLE_STAGE = raw_stage
        return raw_stage

    if _hold_stage(stable, inputs, thresholds):
        return stable

    _STABLE_STAGE = raw_stage
    return raw_stage

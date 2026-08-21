"""参数网格展开与最优选取。"""

from __future__ import annotations

from itertools import product
from typing import Any

MAX_OPTIMIZE_COMBOS = 64


def expand_ma_grid(space: dict[str, list[int]]) -> list[dict[str, int]]:
    """展开 fast/slow 网格；过滤 fast>=slow；超过 MAX_OPTIMIZE_COMBOS 抛 ValueError。"""
    fast_vals = list(space.get("fast_window") or [])
    slow_vals = list(space.get("slow_window") or [])
    if not fast_vals or not slow_vals:
        raise ValueError("space 须包含 fast_window 与 slow_window 非空列表")

    raw = [{"fast_window": f, "slow_window": s} for f, s in product(fast_vals, slow_vals)]
    combos = [c for c in raw if c["fast_window"] < c["slow_window"]]
    if len(combos) > MAX_OPTIMIZE_COMBOS:
        raise ValueError(f"优化组合数 {len(combos)} 超过上限 {MAX_OPTIMIZE_COMBOS}")
    return combos


def pick_best(runs: list[dict[str, Any]], *, objective: str) -> dict[str, Any] | None:
    """按 objective 数值最大选取；None 视为最差。"""
    if not runs:
        return None

    def score(row: dict[str, Any]) -> float:
        val = row.get(objective)
        if val is None:
            return float("-inf")
        try:
            return float(val)
        except (TypeError, ValueError):
            return float("-inf")

    return max(runs, key=score)

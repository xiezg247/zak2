"""自动任务域：调度时间匹配（星期与时刻的解析、匹配）。"""

from __future__ import annotations

import re
from datetime import datetime

WEEKDAY_NAMES = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}

_TIME_RE = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")


def parse_days_of_week(raw: str) -> list[int]:
    """解析 'mon-fri' / 'mon,wed,fri'（支持混合）→ 升序 weekday 索引列表（mon=0）。"""
    days: set[int] = set()
    for item in str(raw).strip().lower().split(","):
        item = item.strip()
        if not item:
            continue
        if "-" in item:
            start_name, end_name = item.split("-", 1)
            if start_name not in WEEKDAY_NAMES or end_name not in WEEKDAY_NAMES:
                raise ValueError(f"非法星期：{item}")
            start, end = WEEKDAY_NAMES[start_name], WEEKDAY_NAMES[end_name]
            if start > end:
                raise ValueError(f"非法星期范围：{item}")
            days.update(range(start, end + 1))
        else:
            if item not in WEEKDAY_NAMES:
                raise ValueError(f"非法星期：{item}")
            days.add(WEEKDAY_NAMES[item])
    if not days:
        raise ValueError("至少需要一个执行星期")
    return sorted(days)


def parse_times(times: list[str]) -> list[str]:
    """校验 'HH:MM' 列表，返回排序去重结果；非法或为空抛 ValueError。"""
    out: set[str] = set()
    for raw in times:
        value = str(raw).strip()
        if not _TIME_RE.fullmatch(value):
            raise ValueError(f"非法时刻：{value}")
        out.add(value)
    if not out:
        raise ValueError("至少需要一个执行时刻")
    return sorted(out)


def matches_now(days: list[int], times: list[str], now: datetime) -> bool:
    """当前时刻是否命中星期列表与时刻列表。"""
    if now.weekday() not in days:
        return False
    hhmm = f"{now.hour:02d}:{now.minute:02d}"
    return hhmm in times

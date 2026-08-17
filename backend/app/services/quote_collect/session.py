"""A 股交易时段（薄：工作日 + 时分，不含节假日日历）。"""

from __future__ import annotations

from datetime import datetime, time
from zoneinfo import ZoneInfo

TZ_SH = ZoneInfo("Asia/Shanghai")

_MORNING_START = time(9, 15)
_MORNING_END = time(11, 30)
_AFTERNOON_START = time(13, 0)
_AFTERNOON_END = time(15, 5)


def is_ashare_trading_session(now: datetime | None = None) -> bool:
    """工作日且落在 09:15–11:30 或 13:00–15:05（Asia/Shanghai）。"""
    dt = now or datetime.now(TZ_SH)
    dt = dt.replace(tzinfo=TZ_SH) if dt.tzinfo is None else dt.astimezone(TZ_SH)
    if dt.weekday() >= 5:
        return False
    t = dt.time()
    if _MORNING_START <= t <= _MORNING_END:
        return True
    return _AFTERNOON_START <= t <= _AFTERNOON_END

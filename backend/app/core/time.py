"""统一时区约定：时间戳用 UTC，交易/业务日期用北京时间（UTC+8）。"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

# 中国标准时间固定 UTC+8，无夏令时
CHINA_TZ = timezone(timedelta(hours=8))


def china_now() -> datetime:
    """当前北京时间（带 tzinfo）。"""
    return datetime.now(CHINA_TZ)


def china_today() -> date:
    """当前北京日期（交易日期语义）。"""
    return datetime.now(CHINA_TZ).date()

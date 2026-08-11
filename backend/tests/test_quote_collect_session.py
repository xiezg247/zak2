from datetime import datetime
from zoneinfo import ZoneInfo

from app.services.quote_collect.session import is_ashare_trading_session

TZ = ZoneInfo("Asia/Shanghai")


def test_morning_open() -> None:
    assert is_ashare_trading_session(datetime(2026, 8, 11, 9, 30, tzinfo=TZ))  # Tue


def test_lunch_skip() -> None:
    assert not is_ashare_trading_session(datetime(2026, 8, 11, 12, 0, tzinfo=TZ))


def test_weekend_skip() -> None:
    assert not is_ashare_trading_session(datetime(2026, 8, 8, 10, 0, tzinfo=TZ))  # Sat


def test_afternoon_edge() -> None:
    assert is_ashare_trading_session(datetime(2026, 8, 11, 15, 0, tzinfo=TZ))
    assert not is_ashare_trading_session(datetime(2026, 8, 11, 15, 6, tzinfo=TZ))

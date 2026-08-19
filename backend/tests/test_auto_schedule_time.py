from __future__ import annotations

from datetime import datetime

import pytest

from app.core.time import CHINA_TZ
from app.services.ops.auto_schedule_time import (
    matches_now,
    parse_days_of_week,
    parse_times,
)

MON = datetime(2026, 8, 17, 9, 35, tzinfo=CHINA_TZ)  # 周一 09:35
SAT = datetime(2026, 8, 22, 9, 35, tzinfo=CHINA_TZ)  # 周六 09:35


def test_parse_days_range() -> None:
    assert parse_days_of_week("mon-fri") == [0, 1, 2, 3, 4]


def test_parse_days_list() -> None:
    assert parse_days_of_week("mon,wed,fri") == [0, 2, 4]


def test_parse_days_mixed() -> None:
    assert parse_days_of_week("mon,wed-fri") == [0, 2, 3, 4]


def test_parse_days_uppercase_ok() -> None:
    assert parse_days_of_week("Mon,Fri") == [0, 4]


def test_parse_days_invalid_raises() -> None:
    with pytest.raises(ValueError):
        parse_days_of_week("monday")


def test_parse_days_empty_raises() -> None:
    with pytest.raises(ValueError):
        parse_days_of_week("")


def test_parse_times_normalizes() -> None:
    assert parse_times(["09:35", "14:00", "09:35"]) == ["09:35", "14:00"]


def test_parse_times_invalid_raises() -> None:
    with pytest.raises(ValueError):
        parse_times(["9:35"])


def test_parse_times_empty_raises() -> None:
    with pytest.raises(ValueError):
        parse_times([])


def test_matches_day_and_time() -> None:
    assert matches_now([0, 1, 2, 3, 4], ["09:35", "14:00"], MON) is True


def test_matches_time_but_wrong_day() -> None:
    assert matches_now([0, 1, 2, 3, 4], ["09:35"], SAT) is False


def test_matches_day_but_wrong_time() -> None:
    assert matches_now([0, 1, 2, 3, 4], ["14:00"], MON) is False

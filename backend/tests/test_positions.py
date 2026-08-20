from __future__ import annotations

import pytest

from app.core.errors import ValidationFailed
from app.domains.watchlist.positions_repo import (
    normalize_cost_price,
    normalize_volume,
    validate_inputs,
)


def test_normalize_cost_price_tick() -> None:
    assert normalize_cost_price(10.555) == 10.56
    assert normalize_cost_price(10.554) == 10.55


def test_normalize_volume_lot() -> None:
    assert normalize_volume(100) == 100
    assert normalize_volume(250) == 200
    assert normalize_volume(50) == 0


def test_validate_rejects_non_lot() -> None:
    with pytest.raises(ValidationFailed) as exc:
        validate_inputs(cost_price=10.0, volume=150, buy_date="2026-06-01")
    assert exc.value.status_code == 400


def test_validate_rejects_future_buy_date() -> None:
    with pytest.raises(ValidationFailed) as exc:
        validate_inputs(cost_price=10.0, volume=100, buy_date="2099-01-01")
    assert exc.value.status_code == 400


def test_validate_ok() -> None:
    validate_inputs(cost_price=10.5, volume=100, buy_date="2026-06-01")

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.services.market.db_ranks import _load_daily_bars, db_rank_fallback


def test_db_rank_fallback_change_pct_ordering() -> None:
    db = MagicMock()
    bars = {
        "SHSE.600519": {
            "symbol": "600519",
            "exchange": "SSE",
            "last_price": 110.0,
            "amount": 1_000_000_000.0,
            "volume": 1000,
        },
        "SHSE.000001": {
            "symbol": "000001",
            "exchange": "SZSE",
            "last_price": 10.0,
            "amount": 500_000_000.0,
            "volume": 2000,
        },
    }
    with (
        patch("app.services.market.db_ranks._latest_trade_dates", return_value=("2024-01-02", "2023-12-29")),
        patch("app.services.market.db_ranks._load_daily_bars", return_value=bars),
        patch(
            "app.services.market.db_ranks._load_prev_closes",
            return_value={"SHSE.600519": 100.0, "SHSE.000001": 9.0},
        ),
        patch("app.services.market.db_ranks._load_daily_basic_factors", return_value={}),
        patch("app.services.market.db_ranks._load_limit_times", return_value={}),
        patch("app.services.market.db_ranks._load_names", return_value={}),
    ):
        rows = db_rank_fallback(db, "change_pct", top_n=10)

    assert len(rows) == 2
    assert rows[0].tf_symbol == "SHSE.000001"  # 11.11% 涨幅更大
    assert rows[0].rank == 1
    assert rows[0].change_pct == pytest.approx(11.11, abs=0.01)
    assert rows[1].tf_symbol == "SHSE.600519"
    assert rows[1].change_pct == pytest.approx(10.0, abs=0.01)
    assert rows[1].vt_symbol == "600519.SSE"


def test_load_daily_bars_amount_converts_qianyuan_to_yuan() -> None:
    db = MagicMock()
    db.execute.return_value.mappings.return_value.all.return_value = [
        {"symbol": "600519", "exchange": "SSE", "close_price": 100.0, "turnover": 50000.0, "volume": 1000}
    ]
    out = _load_daily_bars(db, "2024-01-02")
    assert out["SHSE.600519"]["amount"] == 50_000_000.0  # 50000 千元 × 1000
    assert out["SHSE.600519"]["last_price"] == 100.0

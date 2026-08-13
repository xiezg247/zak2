from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.schemas.screener import PatternRunRequest
from app.services import bars, engine, pattern_screen
from app.services.backtest_engine import load_daily_bars


def test_require_quotes_empty_points_to_collector() -> None:
    store = MagicMock()
    store.available.return_value = True
    store.meta.return_value = {"quote_count": 0}
    with pytest.raises(HTTPException) as ei:
        engine._require_quotes(store)
    assert ei.value.status_code == 503
    assert "quote-collector" in ei.value.detail
    for bad in ("zak 侧", "zak 下载", "使用 zak", "collect_quotes"):
        assert bad not in ei.value.detail


def test_pattern_screen_empty_quotes_points_to_collector() -> None:
    store = MagicMock()
    store.available.return_value = True
    store.meta.return_value = {"quote_count": 0}
    with pytest.raises(HTTPException) as ei:
        pattern_screen.run_pattern_screen(
            PatternRunRequest(pattern_id="ma_bull", top_n=5, max_scan=50),
            db=MagicMock(),
            store=store,
        )
    assert "quote-collector" in ei.value.detail
    for bad in ("zak 侧", "zak 下载", "使用 zak"):
        assert bad not in ei.value.detail


def test_load_daily_bars_insufficient_points_to_ops() -> None:
    db = MagicMock()
    db.scalars.return_value = []  # 0 bars → len < 30
    with pytest.raises(HTTPException) as ei:
        load_daily_bars(
            db,
            vt_symbol="SHSE.600519",
            start_date="2024-01-01",
            end_date="2024-06-01",
        )
    assert ei.value.status_code == 404
    assert "Ops" in ei.value.detail
    for bad in ("zak 侧", "zak 下载", "使用 zak"):
        assert bad not in ei.value.detail


def test_load_bars_empty_points_to_ops() -> None:
    db = MagicMock()
    db.scalars.return_value = []
    with pytest.raises(HTTPException) as ei:
        bars.load_bars(db, symbol="600519", exchange="SHSE")
    assert ei.value.status_code == 404
    assert "Ops" in ei.value.detail
    for bad in ("zak 侧", "zak 下载", "使用 zak"):
        assert bad not in ei.value.detail

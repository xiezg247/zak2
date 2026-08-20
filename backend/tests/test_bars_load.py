from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from app.core.errors import NotFound

from app.services.market import bars


def test_load_bars_empty_daily_ops_copy() -> None:
    db = MagicMock()
    db.scalars.return_value = []
    with pytest.raises(NotFound) as ei:
        bars.load_bars(db, symbol="600519", exchange="SHSE", interval="d")
    assert ei.value.status_code == 404
    assert "Ops" in ei.value.detail
    assert "日 K" in ei.value.detail or "全日 K" in ei.value.detail
    assert "fill_focus_pool_minute" not in ei.value.detail
    for bad in ("zak 侧", "zak 下载", "使用 zak"):
        assert bad not in ei.value.detail


def test_load_bars_empty_1m_points_to_focus_job() -> None:
    db = MagicMock()
    db.scalars.return_value = []
    with pytest.raises(NotFound) as ei:
        bars.load_bars(db, symbol="600519", exchange="SHSE", interval="1m")
    assert ei.value.status_code == 404
    assert "1 分" in ei.value.detail or "1分" in ei.value.detail
    assert "fill_focus_pool_minute" in ei.value.detail
    assert "Ops" in ei.value.detail

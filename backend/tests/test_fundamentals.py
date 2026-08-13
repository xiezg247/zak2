from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.services import fundamentals as fund


def test_invalid_vt_400() -> None:
    db = MagicMock()
    with pytest.raises(HTTPException) as ei:
        fund.get_fundamentals(db, "")
    assert ei.value.status_code == 400


def test_empty_db_returns_nulls() -> None:
    db = MagicMock()
    snap = MagicMock()
    snap.mappings.return_value.first.return_value = None
    meta = MagicMock()
    meta.mappings.return_value.first.return_value = None
    disc = MagicMock()
    disc.mappings.return_value.all.return_value = []
    db.execute.side_effect = [snap, meta, disc]
    out = fund.get_fundamentals(db, "600519.SSE")
    assert out["vt_symbol"] == "600519.SSE"
    assert out["ts_code"] == "600519.SH"
    assert out["snapshot"] is None
    assert out["sync"] is None
    assert out["disclosures"] == []


def test_snapshot_and_disclosures_mapped() -> None:
    db = MagicMock()
    snap_row = {
        "end_date": "20251231",
        "revenue": 1e9,
        "net_income": 1e8,
        "revenue_yoy": 0.1,
        "net_income_yoy": 0.2,
        "roe": 0.15,
        "debt_ratio": 0.4,
    }
    sync_row = {
        "last_sync_at": "t1",
        "latest_end_date": "20251231",
        "periods_count": 4,
        "sync_status": "ok",
        "error_message": "",
    }
    disc_rows = [
        {"end_date": "20251231", "pre_date": "20260110", "ann_date": "", "actual_date": ""},
        {"end_date": "20250930", "pre_date": "", "ann_date": "20251020", "actual_date": ""},
        {"end_date": "20250630", "pre_date": "", "ann_date": "", "actual_date": "20250715"},
        {"end_date": "20250331", "pre_date": "", "ann_date": "", "actual_date": ""},
    ]
    snap = MagicMock()
    snap.mappings.return_value.first.return_value = snap_row
    meta = MagicMock()
    meta.mappings.return_value.first.return_value = sync_row
    disc = MagicMock()
    disc.mappings.return_value.all.return_value = disc_rows[:3]
    db.execute.side_effect = [snap, meta, disc]
    out = fund.get_fundamentals(db, "600519.SSE")
    assert out["snapshot"]["end_date"] == "20251231"
    assert out["snapshot"]["roe"] == 0.15
    assert out["sync"]["periods_count"] == 4
    assert len(out["disclosures"]) == 3
    assert out["disclosures"][0]["end_date"] == "20251231"

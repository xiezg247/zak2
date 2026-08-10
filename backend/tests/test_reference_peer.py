from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.schemas.screener import ReferencePeerRequest
from app.services import reference_peer as peer


def test_vt_to_ts_code() -> None:
    assert peer.vt_to_ts_code("600519.SSE") == "600519.SH"
    assert peer.vt_to_ts_code("000001.SZSE") == "000001.SZ"
    assert peer.vt_to_ts_code("SHSE.600519") == "600519.SH"


def test_scoring_helpers() -> None:
    assert peer.valuation_score(pe=20, mv=1000, ref_pe=20, ref_mv=1000) == 100.0
    assert peer.momentum_score(5.0, 5.0) == 100.0
    assert peer.composite_similarity(val_score=100, mom_score=100) == 100.0
    got = peer.cumulative_return("A", [{"A": 10.0}, {"A": -5.0}])
    assert abs(got - 4.5) < 0.01


def test_run_reference_peer_mocked() -> None:
    basic = [
        {"ts_code": "600519.SH", "close": 1800, "pe_ttm": 30, "circ_mv": 2_000_000, "total_mv": 2_100_000, "turnover_rate": 1},
        {"ts_code": "600000.SH", "close": 10, "pe_ttm": 28, "circ_mv": 1_800_000, "total_mv": 1_900_000, "turnover_rate": 2},
        {"ts_code": "000001.SZ", "close": 12, "pe_ttm": 8, "circ_mv": 500_000, "total_mv": 600_000, "turnover_rate": 3},
    ]
    meta = {
        "600519.SH": {"industry": "白酒", "name": "茅台"},
        "600000.SH": {"industry": "白酒", "name": "同行A"},
        "000001.SZ": {"industry": "银行", "name": "银行B"},
    }
    pct = [{"600519.SH": 1.0, "600000.SH": 1.2, "000001.SZ": -1.0}] * 5

    with (
        patch.object(peer, "_fetch_with_lookback", return_value=(basic, "20260101")),
        patch.object(peer, "_fetch_industry_name_map", return_value=meta),
        patch.object(peer, "_fetch_pct_maps", return_value=pct),
        patch.object(peer.ts, "require_token", return_value="tok"),
        patch.object(peer, "_enrich_from_redis"),
        patch.object(peer.stock_industry, "enrich_rows_from_db") as enrich,
    ):
        result = peer.run_reference_peer(
            ReferencePeerRequest(vt_symbol="600519.SSE", top_n=10, hard_filter_template="aggressive"),
            db=MagicMock(),
        )
    enrich.assert_called_once()
    assert result["source"] == "reference_peer"
    assert "茅台" in result["condition"]
    assert result["row_count"] == 1
    assert result["rows"][0]["name"] == "同行A"
    assert result["rows"][0].get("similarity_score") is not None
    assert result["reference"]["industry"] == "白酒"

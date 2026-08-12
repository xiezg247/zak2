from unittest.mock import MagicMock, patch

from app.schemas.market import RadarCardOut, RadarResonanceEntry, RadarResonanceOut
from app.services import ops_scan_horizon_outlook as m


def test_horizon_writes_rows() -> None:
    db = MagicMock()
    cards = [
        RadarCardOut(
            card_id="c1", title="T", source="synthesized", rows=[{"vt_symbol": "600519.SSE", "name": "茅台"}]
        )
    ]
    resonance = RadarResonanceOut(
        min_cards=2,
        top_n=30,
        total=1,
        entries=[
            RadarResonanceEntry(
                vt_symbol="600519.SSE",
                name="茅台",
                card_count=2,
                card_titles=["T"],
                resonance_score=1.5,
                change_pct=1.0,
                last_price=100.0,
            )
        ],
    )
    with (
        patch.object(m, "list_radar_cards", return_value=cards),
        patch.object(m, "compute_resonance", return_value=resonance),
        patch.object(m, "save_job_run_meta") as save,
        patch.object(m, "_upsert_horizon") as upsert,
    ):
        out = m.scan_horizon_outlook(db)
    assert out["success"] is True
    assert out["skipped"] is False
    assert out["written"] == 1
    assert out["strategy_key"] == "resonance_heuristic"
    upsert.assert_called_once()
    save.assert_called_once()
    assert save.call_args.kwargs["last_success"] is True


def test_horizon_empty_still_success() -> None:
    db = MagicMock()
    with (
        patch.object(m, "list_radar_cards", return_value=[]),
        patch.object(
            m,
            "compute_resonance",
            return_value=RadarResonanceOut(min_cards=2, top_n=30, total=0, entries=[]),
        ),
        patch.object(m, "save_job_run_meta") as save,
        patch.object(m, "_upsert_horizon") as upsert,
    ):
        out = m.scan_horizon_outlook(db)
    assert out["success"] is True
    assert out["skipped"] is False
    assert out["written"] == 0
    upsert.assert_called_once()
    assert save.call_args.kwargs["last_success"] is True

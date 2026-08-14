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
        patch.object(m, "load_first_time_map", return_value={}),
        patch.object(m, "resonance_scan_stats", return_value=(10, 4)),
        patch.object(m, "compute_resonance", return_value=resonance),
        patch.object(m, "vt_with_min_daily_bars", return_value={"600519.SSE"}),
        patch.object(m, "score_predict_rows", return_value=([{"vt_symbol": "600519.SSE"}], 0)),
        patch.object(m, "save_job_run_meta") as save,
        patch.object(m, "_upsert_horizon") as upsert,
        patch.object(m, "upsert_predict") as upsert_p,
    ):
        out = m.scan_horizon_outlook(db)
    assert out["success"] is True
    assert out["skipped"] is False
    assert out["written"] == 1
    assert out["predict_written"] == 1
    assert out["strategy_key"] == "resonance_heuristic"
    upsert.assert_called_once()
    upsert_p.assert_called_once()
    save.assert_called_once()
    assert save.call_args.kwargs["last_success"] is True


def test_horizon_empty_still_success() -> None:
    db = MagicMock()
    with (
        patch.object(m, "list_radar_cards", return_value=[]),
        patch.object(m, "load_first_time_map", return_value={}),
        patch.object(m, "resonance_scan_stats", return_value=(0, 0)),
        patch.object(
            m,
            "compute_resonance",
            return_value=RadarResonanceOut(min_cards=2, top_n=30, total=0, entries=[]),
        ),
        patch.object(m, "vt_with_min_daily_bars", return_value=set()),
        patch.object(m, "score_predict_rows", return_value=([], 0)),
        patch.object(m, "save_job_run_meta") as save,
        patch.object(m, "_upsert_horizon") as upsert,
        patch.object(m, "upsert_predict") as upsert_p,
    ):
        out = m.scan_horizon_outlook(db)
    assert out["success"] is True
    assert out["skipped"] is False
    assert out["written"] == 0
    upsert.assert_called_once()
    upsert_p.assert_called_once()
    assert save.call_args.kwargs["last_success"] is True


def test_horizon_predict_phase_failure_still_success() -> None:
    db = MagicMock()
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
            )
        ],
    )
    with (
        patch.object(m, "list_radar_cards", return_value=[]),
        patch.object(m, "load_first_time_map", return_value={}),
        patch.object(m, "resonance_scan_stats", return_value=(1, 0)),
        patch.object(m, "compute_resonance", return_value=resonance),
        patch.object(m, "vt_with_min_daily_bars", side_effect=RuntimeError("db down")),
        patch.object(m, "save_job_run_meta"),
        patch.object(m, "_upsert_horizon") as upsert,
        patch.object(m, "upsert_predict") as upsert_p,
    ):
        out = m.scan_horizon_outlook(db)
    assert out["success"] is True
    assert out.get("predict_error")
    assert "predict_error" in (out.get("message") or "")
    upsert.assert_called_once()
    upsert_p.assert_not_called()

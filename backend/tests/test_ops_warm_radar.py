from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.schemas.market import RadarCardOut
from app.services import ops_warm_radar as warm


def test_warm_upserts_cards() -> None:
    db = MagicMock()
    cards = [
        RadarCardOut(
            card_id="leader_pick",
            title="选股·龙头",
            subtitle="",
            source="synthesized",
            rows=[],
            empty_message="",
        ),
        RadarCardOut(
            card_id="discovery_limit_ladder",
            title="发现·连板梯队",
            subtitle="2026-08-11",
            source="synthesized",
            rows=[{"vt_symbol": "SHSE.600000", "role": "最高板"}],
            empty_message="",
        ),
    ]
    with patch("app.services.ops_warm_radar.build_synthesized_cards", return_value=cards), patch(
        "app.services.ops_warm_radar.save_job_run_meta"
    ):
        out = warm.warm_radar_card_snapshots(db)
    assert out["success"] is True
    assert out.get("written", 0) == 2
    assert db.execute.call_count == 2
    db.commit.assert_called_once()

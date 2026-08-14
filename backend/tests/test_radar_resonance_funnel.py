from app.schemas.market import RadarCardOut
from app.services.radar_resonance import resonance_scan_stats


def test_resonance_scan_stats_excluded():
    cards = [
        RadarCardOut(
            card_id="leader_pick",
            title="A",
            source="s",
            rows=[{"vt_symbol": "600519.SSE"}],
        ),
        RadarCardOut(
            card_id="discovery_change_top",
            title="B",
            source="s",
            rows=[{"vt_symbol": "600519.SSE"}, {"vt_symbol": "000001.SZSE"}],
        ),
    ]
    scanned, excluded = resonance_scan_stats(cards, min_cards=2)
    assert scanned == 2
    assert excluded == 1

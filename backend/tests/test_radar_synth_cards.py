from unittest.mock import MagicMock, patch

from app.services import radar as radar_svc


def test_synth_limit_break_filters_open_times():
    db = MagicMock()
    with (
        patch.object(radar_svc, "_synth_leader_pick", return_value=MagicMock(card_id="leader_pick")),
        patch.object(radar_svc, "_synth_limit_ladder", return_value=MagicMock(card_id="discovery_limit_ladder")),
        patch.object(radar_svc, "_synth_sector_hot", return_value=MagicMock(card_id="sector_flow_hot")),
        patch.object(radar_svc, "_synth_change_top", return_value=MagicMock(card_id="discovery_change_top")),
        patch.object(radar_svc, "_synth_volume_surge", return_value=None),
        patch(
            "app.services.limit_list_store.list_limit_list",
            return_value={
                "trade_date": "20260814",
                "rows": [
                    {"vt_symbol": "600000.SSE", "name": "浦发", "open_times": 2},
                    {"vt_symbol": "600519.SSE", "name": "茅台", "open_times": 0},
                ],
            },
        ),
    ):
        cards = radar_svc.build_synthesized_cards(db)
    break_cards = [c for c in cards if getattr(c, "card_id", None) == "discovery_limit_break"]
    assert len(break_cards) == 1
    assert break_cards[0].rows[0]["vt_symbol"] == "600000.SSE"
    assert all(float(r.get("open_times") or 0) > 0 for r in break_cards[0].rows)


def test_synth_volume_surge_omits_when_empty():
    store = MagicMock()
    store.available.return_value = True
    store.list_rank.return_value = [("SHSE.600519", 1.5)]
    with (
        patch.object(radar_svc, "_synth_leader_pick", return_value=MagicMock(card_id="leader_pick")),
        patch.object(radar_svc, "_synth_limit_ladder", return_value=MagicMock(card_id="discovery_limit_ladder")),
        patch.object(radar_svc, "_synth_sector_hot", return_value=MagicMock(card_id="sector_flow_hot")),
        patch.object(radar_svc, "_synth_change_top", return_value=MagicMock(card_id="discovery_change_top")),
        patch.object(radar_svc, "_synth_limit_break", return_value=None),
        patch.object(radar_svc, "get_quote_store", return_value=store),
    ):
        cards = radar_svc.build_synthesized_cards(MagicMock())
    assert not any(getattr(c, "card_id", None) == "discovery_volume_surge" for c in cards)

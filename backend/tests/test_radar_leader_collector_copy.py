from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.services import leader_screen, radar


def test_synth_change_top_empty_points_to_collector() -> None:
    store = MagicMock()
    store.available.return_value = True
    store.list_rank.return_value = []
    with patch.object(radar, "get_quote_store", return_value=store):
        card = radar._synth_change_top()
    assert "quote-collector" in (card.empty_message or "")
    assert "collect_quotes" not in (card.empty_message or "")


def test_synth_leader_pick_empty_points_to_collector() -> None:
    store = MagicMock()
    store.available.return_value = True
    store.meta.return_value = {"quote_count": 0}
    with patch.object(leader_screen, "get_quote_store", return_value=store):
        rows, _sub, empty = leader_screen.synth_leader_pick_rows(MagicMock(), top_n=5)
    assert rows == []
    assert "quote-collector" in empty
    assert "collect_quotes" not in empty

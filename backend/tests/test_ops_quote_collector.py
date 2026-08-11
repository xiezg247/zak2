from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from app.services.quote_collect.control import force_collect
from app.services.quote_collect.heartbeat import is_heartbeat_fresh


def test_heartbeat_fresh() -> None:
    ts = datetime.now(timezone.utc).isoformat()
    assert is_heartbeat_fresh({"ts": ts})
    old = (datetime.now(timezone.utc) - timedelta(seconds=120)).isoformat()
    assert not is_heartbeat_fresh({"ts": old})


def test_force_without_collector() -> None:
    client = MagicMock()
    with patch("app.services.quote_collect.control.read_heartbeat", return_value=None):
        out = force_collect(client)
    assert out["success"] is False
    assert "collector" in out["message"].lower() or "quote_collector" in out["message"]


def test_force_with_fresh_heartbeat() -> None:
    client = MagicMock()
    hb = {"ts": datetime.now(timezone.utc).isoformat(), "status": "idle"}
    with patch("app.services.quote_collect.control.read_heartbeat", return_value=hb):
        out = force_collect(client)
    assert out["success"] is True
    client.publish.assert_called()

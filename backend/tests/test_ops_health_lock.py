from unittest.mock import MagicMock, patch

from app.services.ops import health as ops_health


def test_health_scheduler_lock_has_ok() -> None:
    db = MagicMock()
    with (
        patch.object(ops_health, "get_quote_store") as gs,
        patch.object(ops_health, "collector_health", return_value={}),
        patch.object(ops_health.mcp_client, "probe_connection", return_value={}),
    ):
        store = MagicMock()
        store.meta.return_value = {"available": True, "updated_at": None, "quote_count": 0}
        gs.return_value = store
        snap = ops_health.health_snapshot(db)
    assert snap.scheduler_lock.ok is True
    assert snap.scheduler_lock.key_prefix

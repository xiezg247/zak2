from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.core.security import create_access_token
from app.main import app
from app.services.quote_notify_hub import QuoteNotifyHub, get_quote_notify_hub


def test_ws_rejects_missing_token() -> None:
    client = TestClient(app)
    with pytest.raises(WebSocketDisconnect), client.websocket_connect("/api/v1/ws/quotes"):
        pass


def test_ws_hello_with_valid_token() -> None:
    token = create_access_token(user_id="u-test", username="tester")
    with patch("app.api.v1.ws._user_active", return_value=True):
        client = TestClient(app)
        with client.websocket_connect(f"/api/v1/ws/quotes?token={token}") as ws:
            data = ws.receive_json()
            assert data.get("type") == "hello"


@pytest.mark.asyncio
async def test_hub_broadcast_seq() -> None:
    hub = QuoteNotifyHub()
    ws = MagicMock()
    ws.send_json = AsyncMock()
    await hub.register(ws)
    await hub.broadcast_seq(42)
    ws.send_json.assert_awaited()
    args = ws.send_json.await_args.args[0]
    assert args["type"] == "quotes_updated"
    assert args["seq"] == 42
    await hub.unregister(ws)


def test_get_hub_singleton() -> None:
    a = get_quote_notify_hub()
    b = get_quote_notify_hub()
    assert a is b

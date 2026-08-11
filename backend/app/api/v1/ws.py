"""WebSocket：行情更新通知（seq）。"""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from sqlalchemy import select

from app.core.db import SessionLocal
from app.core.redis_keys import NOTIFY_CHANNEL
from app.core.security import decode_access_token
from app.models.user import User
from app.services.quote_notify_hub import get_quote_notify_hub

logger = logging.getLogger(__name__)
router = APIRouter(tags=["ws"])


def _user_id_from_token(token: str) -> str | None:
    try:
        payload = decode_access_token(token)
    except Exception:  # noqa: BLE001
        return None
    user_id = str(payload.get("sub") or "")
    return user_id or None


def _user_active(user_id: str) -> bool:
    db = SessionLocal()
    try:
        user = db.scalar(select(User).where(User.id == user_id))
        return bool(user and user.is_active)
    finally:
        db.close()


@router.websocket("/ws/quotes")
async def ws_quotes(websocket: WebSocket, token: str = Query(default="")) -> None:
    user_id = _user_id_from_token(token.strip())
    if not user_id or not _user_active(user_id):
        await websocket.close(code=4401)
        return

    await websocket.accept()
    hub = get_quote_notify_hub()
    await hub.register(websocket)
    try:
        await websocket.send_json({"type": "hello", "channel": NOTIFY_CHANNEL})
        while True:
            try:
                # 客户端可发 ping；超时则服务端发 ping
                raw = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                if raw.strip().lower() in {"ping", '{"type":"ping"}'}:
                    await websocket.send_json({"type": "pong"})
            except TimeoutError:
                try:
                    await websocket.send_json({"type": "ping"})
                except Exception:  # noqa: BLE001
                    break
    except WebSocketDisconnect:
        pass
    except Exception:  # noqa: BLE001
        logger.debug("ws_quotes ended", exc_info=True)
    finally:
        await hub.unregister(websocket)

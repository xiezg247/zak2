"""Redis zak:notify:quotes → WebSocket 广播。"""

from __future__ import annotations

import asyncio
import logging
import threading
from typing import Any

import redis
from fastapi import WebSocket

from app.core.settings import get_settings

logger = logging.getLogger(__name__)

QUOTE_NOTIFY_CHANNEL = "zak:notify:quotes"


class QuoteNotifyHub:
    def __init__(self) -> None:
        self._clients: set[WebSocket] = set()
        self._lock = asyncio.Lock()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self, loop: asyncio.AbstractEventLoop) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._loop = loop
        self._stop.clear()
        self._thread = threading.Thread(target=self._listen_loop, name="quote-notify", daemon=True)
        self._thread.start()
        logger.info("quote notify listener started")

    def stop(self) -> None:
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        self._thread = None
        self._loop = None

    async def register(self, ws: WebSocket) -> None:
        async with self._lock:
            self._clients.add(ws)

    async def unregister(self, ws: WebSocket) -> None:
        async with self._lock:
            self._clients.discard(ws)

    async def broadcast_seq(self, seq: int) -> None:
        payload: dict[str, Any] = {"type": "quotes_updated", "seq": seq}
        async with self._lock:
            clients = list(self._clients)
        dead: list[WebSocket] = []
        for ws in clients:
            try:
                await ws.send_json(payload)
            except Exception:  # noqa: BLE001
                dead.append(ws)
        if dead:
            async with self._lock:
                for ws in dead:
                    self._clients.discard(ws)

    def notify_from_thread(self, seq: int) -> None:
        loop = self._loop
        if loop is None or loop.is_closed():
            return
        try:
            asyncio.run_coroutine_threadsafe(self.broadcast_seq(seq), loop)
        except Exception:  # noqa: BLE001
            logger.debug("notify_from_thread failed seq=%s", seq, exc_info=True)

    def _listen_loop(self) -> None:
        url = get_settings().redis_url
        client: redis.Redis | None = None
        pubsub = None
        try:
            client = redis.Redis.from_url(url, decode_responses=True)
            client.ping()
            pubsub = client.pubsub(ignore_subscribe_messages=True)
            pubsub.subscribe(QUOTE_NOTIFY_CHANNEL)
            while not self._stop.is_set():
                message = pubsub.get_message(timeout=1.0)
                if not message or message.get("type") != "message":
                    continue
                raw = message.get("data")
                text = str(raw or "").strip()
                try:
                    seq = int(text)
                except ValueError:
                    continue
                if seq > 0:
                    self.notify_from_thread(seq)
        except Exception:  # noqa: BLE001
            logger.warning("quote notify listener stopped / redis unavailable", exc_info=True)
        finally:
            try:
                if pubsub is not None:
                    pubsub.unsubscribe(QUOTE_NOTIFY_CHANNEL)
                    pubsub.close()
            except Exception:  # noqa: BLE001
                pass
            try:
                if client is not None:
                    client.close()
            except Exception:  # noqa: BLE001
                pass


_hub: QuoteNotifyHub | None = None


def get_quote_notify_hub() -> QuoteNotifyHub:
    global _hub
    if _hub is None:
        _hub = QuoteNotifyHub()
    return _hub

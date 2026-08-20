"""情绪周期快照短 TTL 缓存（Redis 优先，否则进程内内存）。"""

from __future__ import annotations

import json
import os
import time
from contextlib import suppress
from typing import cast

import redis

from app.domains.market.schemas import EmotionCycleOut
from app.domains.market.quotes import get_quote_store

CACHE_KEY = "zak2:emotion_cycle:v1"

_mem: tuple[float, EmotionCycleOut] | None = None


def cache_ttl_sec() -> int:
    raw = os.environ.get("EMOTION_CYCLE_CACHE_TTL_SEC", "60")
    try:
        val = int(raw)
    except (TypeError, ValueError):
        val = 60
    return max(5, min(600, val))


def _redis_client() -> redis.Redis | None:
    store = get_quote_store()
    if not store.available():
        return None
    return store._conn()


def cache_get() -> EmotionCycleOut | None:
    global _mem
    client = _redis_client()
    if client is not None:
        try:
            raw = client.get(CACHE_KEY)
            if raw:
                parsed = json.loads(cast(str, raw))
                if isinstance(parsed, dict):
                    return EmotionCycleOut(**parsed)
        except (redis.RedisError, TypeError, ValueError, json.JSONDecodeError):
            return None
        return None

    if _mem is not None:
        expires_at, payload = _mem
        if time.monotonic() < expires_at:
            return payload
        _mem = None
    return None


def cache_set(payload: EmotionCycleOut) -> None:
    global _mem
    ttl = cache_ttl_sec()
    client = _redis_client()
    if client is not None:
        with suppress(redis.RedisError):
            client.setex(CACHE_KEY, ttl, json.dumps(payload.model_dump(mode="json"), ensure_ascii=False))
        return

    _mem = (time.monotonic() + ttl, payload)


def cache_invalidate() -> None:
    global _mem
    client = _redis_client()
    if client is not None:
        with suppress(redis.RedisError):
            client.delete(CACHE_KEY)
    _mem = None

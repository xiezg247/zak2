"""ARQ worker 侧 bars 互斥锁。"""

from __future__ import annotations

import logging
from typing import Any

import redis

from app.core.redis_keys import ARQ_BARS_LOCK_KEY
from app.core.settings import get_settings
from app.services.scheduler_lock import clamp_ttl, make_token

_logger = logging.getLogger(__name__)

BARS_JOBS = frozenset(
    {"fill_watchlist_bars", "batch_fill_stale", "batch_download_universe"}
)

_RELEASE_LUA = """
if redis.call("get", KEYS[1]) == ARGV[1] then
  return redis.call("del", KEYS[1])
else
  return 0
end
"""


def _redis_client() -> redis.Redis:
    return redis.Redis.from_url(get_settings().redis_url, decode_responses=True)


def try_acquire_bars(*, token: str | None = None, client: Any | None = None) -> str | None:
    """成功返回 token，失败返回 None。"""
    tok = token or make_token()
    c = client if client is not None else _redis_client()
    ttl = clamp_ttl(get_settings().scheduler_lock_ttl_seconds)
    try:
        ok = bool(c.set(ARQ_BARS_LOCK_KEY, tok, nx=True, ex=ttl))
    except redis.RedisError:
        _logger.exception("bars lock acquire failed")
        return None
    return tok if ok else None


def release_bars(token: str, *, client: Any | None = None) -> None:
    c = client if client is not None else _redis_client()
    try:
        c.eval(_RELEASE_LUA, 1, ARQ_BARS_LOCK_KEY, token)
    except redis.RedisError:
        _logger.exception("bars lock release failed")

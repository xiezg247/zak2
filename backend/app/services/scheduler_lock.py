"""Redis 分布式 job 锁：多 API 副本防同一 job 双跑。"""

from __future__ import annotations

import logging
import os
import socket
import uuid
from typing import Any

import redis

from app.core.settings import get_settings

_logger = logging.getLogger(__name__)

LOCK_KEY_PREFIX = "zak2:scheduler:lock:"
DEFAULT_TTL = 1800
_MIN_TTL = 60
_MAX_TTL = 7200

_RELEASE_LUA = """
if redis.call("get", KEYS[1]) == ARGV[1] then
  return redis.call("del", KEYS[1])
else
  return 0
end
"""


def clamp_ttl(seconds: int) -> int:
    return max(_MIN_TTL, min(_MAX_TTL, seconds))


def lock_key(job_id: str) -> str:
    return f"{LOCK_KEY_PREFIX}{job_id}"


def make_token() -> str:
    return f"{socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex[:8]}"


def _redis_client() -> redis.Redis:
    return redis.Redis.from_url(get_settings().redis_url, decode_responses=True)


def try_acquire(
    job_id: str,
    *,
    token: str,
    ttl: int | None = None,
    client: Any | None = None,
) -> bool:
    c = client if client is not None else _redis_client()
    raw_ttl = ttl if ttl is not None else get_settings().scheduler_lock_ttl_seconds
    effective_ttl = clamp_ttl(raw_ttl)
    try:
        return bool(c.set(lock_key(job_id), token, nx=True, ex=effective_ttl))
    except redis.RedisError:
        _logger.exception("scheduler lock acquire failed for %s", job_id)
        return False


def release(job_id: str, token: str, *, client: Any | None = None) -> None:
    c = client if client is not None else _redis_client()
    try:
        c.eval(_RELEASE_LUA, 1, lock_key(job_id), token)
    except redis.RedisError:
        _logger.exception("scheduler lock release failed for %s", job_id)

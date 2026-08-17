"""登录失败限流：按 username 与 IP 双维度防密码爆破。

固定窗口计数：窗口内失败次数达到阈值即锁定（即使密码正确也拒绝）。
Redis 不可用时 fail-open（不阻断登录），避免登录路径被 Redis 故障拖垮。
"""

from __future__ import annotations

from typing import Any, cast

import redis

from app.core.redis_keys import AUTH_FAIL_IP_KEY_FMT, AUTH_FAIL_USER_KEY_FMT
from app.core.settings import get_settings


def _client() -> redis.Redis:
    return redis.Redis.from_url(get_settings().redis_url, decode_responses=True)


def _keys(username: str, ip: str | None) -> list[str]:
    keys = [AUTH_FAIL_USER_KEY_FMT.format(username=username.strip().lower())]
    if ip:
        keys.append(AUTH_FAIL_IP_KEY_FMT.format(ip=ip))
    return keys


def _is_locked(client: redis.Redis, key: str, threshold: int) -> bool:
    raw = client.get(key)
    if raw is None:
        return False
    try:
        return int(cast(Any, raw)) >= threshold
    except (TypeError, ValueError):
        return False


def is_locked(username: str, ip: str | None) -> bool:
    """是否处于锁定状态。Redis 异常时返回 False（fail-open）。"""
    settings = get_settings()
    threshold = max(1, int(settings.login_max_failures))
    try:
        client = _client()
        return any(_is_locked(client, key, threshold) for key in _keys(username, ip))
    except redis.RedisError:
        return False


def record_failure(username: str, ip: str | None) -> None:
    """记录一次登录失败。Redis 异常时静默忽略。"""
    settings = get_settings()
    window = max(1, int(settings.login_lock_window_seconds))
    try:
        client = _client()
        for key in _keys(username, ip):
            count = client.incr(key)
            if count == 1:
                client.expire(key, window)
    except redis.RedisError:
        return


def reset(username: str, ip: str | None) -> None:
    """登录成功后清空失败计数。Redis 异常时静默忽略。"""
    try:
        client = _client()
        for key in _keys(username, ip):
            client.delete(key)
    except redis.RedisError:
        return

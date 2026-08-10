"""scheduler_lock 单测（mock Redis，不打真连接）。"""

from __future__ import annotations

from unittest.mock import MagicMock

import redis

from app.services import scheduler_lock as sl


def test_clamp_ttl() -> None:
    assert sl.clamp_ttl(10) == 60
    assert sl.clamp_ttl(1800) == 1800
    assert sl.clamp_ttl(99999) == 7200


def test_try_acquire_ok() -> None:
    client = MagicMock()
    client.set.return_value = True
    assert sl.try_acquire("purge_expired", token="t1", client=client) is True
    client.set.assert_called()


def test_try_acquire_busy() -> None:
    client = MagicMock()
    client.set.return_value = None
    assert sl.try_acquire("purge_expired", token="t1", client=client) is False


def test_try_acquire_redis_error() -> None:
    client = MagicMock()
    client.set.side_effect = redis.RedisError("down")
    assert sl.try_acquire("purge_expired", token="t1", client=client) is False


def test_release_only_own_token() -> None:
    client = MagicMock()
    client.eval.return_value = 1
    sl.release("purge_expired", "t1", client=client)
    client.eval.assert_called_once()

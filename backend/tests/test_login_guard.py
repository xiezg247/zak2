"""login_guard 登录限流单测（mock Redis，不依赖真实服务）。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from redis import RedisError

from app.domains.auth import login_guard


def _mock_client(**overrides: object) -> MagicMock:
    client = MagicMock()
    client.get.return_value = None
    client.incr.return_value = 1
    for k, v in overrides.items():
        setattr(client, k, MagicMock(return_value=v))
    return client


def test_is_locked_true_at_threshold() -> None:
    client = _mock_client(get="5")
    with patch.object(login_guard, "_client", return_value=client):
        assert login_guard.is_locked("demo", "1.2.3.4") is True


def test_is_locked_false_below_threshold() -> None:
    client = _mock_client(get="2")
    with patch.object(login_guard, "_client", return_value=client):
        assert login_guard.is_locked("demo", "1.2.3.4") is False


def test_is_locked_false_when_no_key() -> None:
    client = _mock_client(get=None)
    with patch.object(login_guard, "_client", return_value=client):
        assert login_guard.is_locked("demo", "1.2.3.4") is False


def test_is_locked_fail_open_on_redis_error() -> None:
    client = _mock_client()
    client.get.side_effect = RedisError("down")
    with patch.object(login_guard, "_client", return_value=client):
        assert login_guard.is_locked("demo", "1.2.3.4") is False


def test_record_failure_sets_expire_on_first() -> None:
    client = _mock_client(incr=1)
    with patch.object(login_guard, "_client", return_value=client):
        login_guard.record_failure("demo", "1.2.3.4")
    # username + ip 两个 key，首个计数需设过期
    assert client.expire.call_count == 2


def test_record_failure_no_expire_on_subsequent() -> None:
    client = _mock_client(incr=3)
    with patch.object(login_guard, "_client", return_value=client):
        login_guard.record_failure("demo", "1.2.3.4")
    client.expire.assert_not_called()


def test_record_failure_silent_on_redis_error() -> None:
    client = _mock_client()
    client.incr.side_effect = RedisError("down")
    with patch.object(login_guard, "_client", return_value=client):
        login_guard.record_failure("demo", "1.2.3.4")


def test_reset_deletes_user_and_ip_keys() -> None:
    client = _mock_client()
    with patch.object(login_guard, "_client", return_value=client):
        login_guard.reset("Demo ", "1.2.3.4")
    assert client.delete.call_count == 2


def test_reset_silent_on_redis_error() -> None:
    client = _mock_client()
    client.delete.side_effect = RedisError("down")
    with patch.object(login_guard, "_client", return_value=client):
        login_guard.reset("demo", "1.2.3.4")


def test_username_normalized_in_key() -> None:
    client = _mock_client()
    with patch.object(login_guard, "_client", return_value=client):
        login_guard.record_failure("  Demo  ", None)
    # 仅 username 一个 key，且已 strip + lower
    args, _ = client.incr.call_args
    assert args[0].endswith(":demo")

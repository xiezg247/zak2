from __future__ import annotations

from unittest.mock import MagicMock

from app.core.redis_keys import ARQ_BARS_LOCK_KEY
from app.services import bars_lock as bl


def test_try_acquire_bars_sets_nx() -> None:
    client = MagicMock()
    client.set.return_value = True
    tok = bl.try_acquire_bars(token="t1", client=client)
    assert tok == "t1"
    assert client.set.call_args.args[0] == ARQ_BARS_LOCK_KEY


def test_try_acquire_bars_fails() -> None:
    client = MagicMock()
    client.set.return_value = False
    assert bl.try_acquire_bars(token="t1", client=client) is None

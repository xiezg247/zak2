from unittest.mock import MagicMock

from app.core.redis_keys import META_SEQ_KEY, NOTIFY_CHANNEL, QUOTE_KEY_FMT, RANK_KEY_FMT
from app.services.quote_factor_patch import apply_factor_patches


def test_apply_skips_missing_keys_no_publish() -> None:
    client = MagicMock()
    client.exists.return_value = 0
    out = apply_factor_patches(client, {"SHSE.600519": {"turnover_rate": 1.2, "volume_ratio": 2.0}})
    assert out["updated"] == 0
    assert out["seq"] is None
    assert out["published"] is False
    client.hset.assert_not_called()
    client.publish.assert_not_called()
    client.incr.assert_not_called()
    client.pipeline.assert_not_called()


def test_apply_patches_existing_and_rebuilds_ranks() -> None:
    client = MagicMock()
    client.exists.return_value = 1
    pipe = MagicMock()
    pipe.execute.return_value = [None, None, None, None, None, None, 42]
    client.pipeline.return_value = pipe
    patches = {
        "SHSE.600519": {
            "turnover_rate": 1.5,
            "volume_ratio": 2.0,
            "total_mv": 100.0,
            "circ_mv": 80.0,
            "net_mf_amount": -3.0,
        }
    }
    out = apply_factor_patches(client, patches)
    assert out["updated"] == 1
    assert out["seq"] == 42
    assert out["published"] is True

    key = QUOTE_KEY_FMT.format(symbol="SHSE.600519")
    client.hset.assert_called_once()
    hset_kwargs = client.hset.call_args.kwargs
    assert client.hset.call_args.args[0] == key or hset_kwargs.get("name") == key
    mapping = hset_kwargs.get("mapping") or client.hset.call_args.args[1]
    assert mapping == {
        "turnover_rate": "1.5",
        "volume_ratio": "2.0",
        "total_mv": "100.0",
        "circ_mv": "80.0",
        "net_mf_amount": "-3.0",
    }

    client.pipeline.assert_called_once_with(transaction=False)
    for field in ("turnover_rate", "volume_ratio", "net_mf_amount"):
        pipe.delete.assert_any_call(RANK_KEY_FMT.format(field=field))
    pipe.zadd.assert_any_call(
        RANK_KEY_FMT.format(field="turnover_rate"), {"SHSE.600519": 1.5}
    )
    pipe.zadd.assert_any_call(
        RANK_KEY_FMT.format(field="volume_ratio"), {"SHSE.600519": 2.0}
    )
    pipe.zadd.assert_any_call(
        RANK_KEY_FMT.format(field="net_mf_amount"), {"SHSE.600519": -3.0}
    )
    pipe.incr.assert_called_once_with(META_SEQ_KEY)
    pipe.execute.assert_called_once()
    client.publish.assert_called_with(NOTIFY_CHANNEL, "42")

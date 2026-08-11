from app.core import redis_keys


def test_key_prefix_is_zak2() -> None:
    assert redis_keys.KEY_PREFIX == "zak2"
    assert redis_keys.NOTIFY_CHANNEL == "zak2:notify:quotes"
    assert redis_keys.QUOTE_KEY_FMT.format(symbol="SHSE.600519") == "zak2:quote:SHSE.600519"
    assert "zak:" not in redis_keys.NOTIFY_CHANNEL.replace("zak2:", "")

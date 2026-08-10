from app.services.symbols import (
    normalize_exchange,
    parse_flexible_symbol,
    parse_vt_symbol,
    to_tf_symbol,
    to_vt_symbol,
)


def test_symbol_conversions() -> None:
    assert normalize_exchange("SHSE") == "SSE"
    assert to_tf_symbol("600519", "SSE") == "SHSE.600519"
    assert to_vt_symbol("600519", "SSE") == "600519.SSE"
    assert parse_vt_symbol("000001.SZSE") == ("000001", "SZSE")
    assert parse_flexible_symbol("SHSE.600519") == ("600519", "SSE")
    assert parse_flexible_symbol("600519") == ("600519", "SSE")
    assert parse_flexible_symbol("000001") == ("000001", "SZSE")

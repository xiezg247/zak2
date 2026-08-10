from app.services.presets import list_presets
from app.services.tushare_screener import ts_code_to_tf


def test_limit_up_and_low_pe_implemented() -> None:
    by_name = {p.name: p for p in list_presets()}
    assert by_name["涨停股"].implemented is True
    assert by_name["低 PE"].implemented is True
    assert by_name["涨停股"].rule_kind == "limit_up"
    assert by_name["低 PE"].rule_kind == "low_pe"
    assert by_name["中大盘"].implemented is True
    assert by_name["主力净流入"].implemented is True


def test_ts_code_to_tf() -> None:
    assert ts_code_to_tf("600519.SH") == "SHSE.600519"
    assert ts_code_to_tf("000001.SZ") == "SZSE.000001"

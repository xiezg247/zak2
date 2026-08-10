from app.services.sector import list_sector_flow, list_trade_dates


def test_sector_kind_validation_via_import() -> None:
    # smoke: module importable
    assert callable(list_sector_flow)
    assert callable(list_trade_dates)

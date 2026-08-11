from app.services.zak_import import (
    DEFAULT_COPY_TABLES,
    SERIAL_ID_TABLES,
    tables_for_import,
)


def test_default_skips_bars() -> None:
    tables = tables_for_import(with_market_sync=False)
    assert "public.dbbardata" not in tables
    assert "auth.users" in tables


def test_market_flag_adds_universe() -> None:
    assert "app.universe" in tables_for_import(with_market_sync=True)


def test_serial_id_tables_are_in_default_copy() -> None:
    default = set(DEFAULT_COPY_TABLES)
    for t in SERIAL_ID_TABLES:
        assert t in default
    assert "app.stock_note_entries" in SERIAL_ID_TABLES
    assert "chat.messages" in SERIAL_ID_TABLES
    assert "app.web_team_reports" in SERIAL_ID_TABLES

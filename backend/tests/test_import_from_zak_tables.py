from psycopg.types.json import Json

from app.services.zak_import import (
    DEFAULT_COPY_TABLES,
    SERIAL_ID_TABLES,
    adapt_row_for_insert,
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
    assert "app.stock_analysis_reports" in SERIAL_ID_TABLES
    assert "app.valuation_history" in DEFAULT_COPY_TABLES
    assert "chat.llm_tool_calls" in DEFAULT_COPY_TABLES


def test_adapt_row_wraps_jsonb_values() -> None:
    row = {"name": "x", "value_json": {"a": 1}, "flag": True}
    out = adapt_row_for_insert(row, {"value_json"})
    assert out["name"] == "x"
    assert out["flag"] is True
    assert isinstance(out["value_json"], Json)
    assert out["value_json"].obj == {"a": 1}

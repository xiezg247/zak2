import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "alembic"))
from ddl import public_bars as pb


def test_public_bar_table_ddl_contains_core_objects() -> None:
    blob = "\n".join(pb.PUBLIC_BAR_TABLE_UP)
    assert "CREATE TABLE IF NOT EXISTS public.dbbardata" in blob
    assert "CREATE TABLE IF NOT EXISTS public.dbbaroverview" in blob
    assert "dbbardata_symbol_exchange_interval_datetime" in blob
    assert "dbbaroverview_symbol_exchange_interval" in blob
    assert "open_price" in blob and "close_price" in blob


def test_public_bar_index_ddl_unchanged_names() -> None:
    blob = "\n".join(pb.PUBLIC_BAR_INDEX_UP)
    assert "ix_dbbardata_daily_symbol_exchange_dt" in blob
    assert "ix_dbbardata_daily_interval_sym_ex_dt" in blob
    assert "ix_dbbardata_daily_dt_brin" in blob

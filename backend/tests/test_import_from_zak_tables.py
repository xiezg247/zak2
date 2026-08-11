from app.services.zak_import import tables_for_import


def test_default_skips_bars() -> None:
    tables = tables_for_import(with_market_sync=False)
    assert "public.dbbardata" not in tables
    assert "auth.users" in tables


def test_market_flag_adds_universe() -> None:
    assert "app.universe" in tables_for_import(with_market_sync=True)

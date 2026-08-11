from pathlib import Path

import app.services.ops_sync_limit_list as limit_list
import app.services.ops_sync_stock_industry as stock_industry


def test_ops_sync_stock_industry_has_no_create_table_ddl() -> None:
    src = Path(stock_industry.__file__).read_text(encoding="utf-8")
    assert "CREATE TABLE IF NOT EXISTS" not in src


def test_ops_sync_limit_list_has_no_create_table_ddl() -> None:
    src = Path(limit_list.__file__).read_text(encoding="utf-8")
    assert "CREATE TABLE IF NOT EXISTS" not in src

"""从 app.stock_industry 读侧补全 QuoteRow 空行业。"""

from __future__ import annotations

import logging

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.quotes import QuoteRow
from app.services.symbols import to_tf_symbol

_logger = logging.getLogger(__name__)

_LOAD_SQL = text("SELECT symbol, exchange, industry FROM app.stock_industry")

_LIST_INDUSTRY_NAMES_SQL = text(
    "SELECT DISTINCT industry FROM app.stock_industry WHERE TRIM(industry) <> '' ORDER BY industry"
)


def load_industry_map(db: Session) -> dict[str, str]:
    try:
        rows = db.execute(_LOAD_SQL).mappings()
    except Exception as exc:  # noqa: BLE001
        _logger.warning("load_industry_map failed: %s", exc)
        return {}

    mapping: dict[str, str] = {}
    for row in rows:
        industry = str(row.get("industry") or "").strip()
        if not industry:
            continue
        tf = to_tf_symbol(str(row["symbol"]), str(row["exchange"]))
        mapping[tf] = industry
    return mapping


def list_industry_names(db: Session) -> list[str]:
    try:
        return [str(name).strip() for name in db.execute(_LIST_INDUSTRY_NAMES_SQL).scalars().all()]
    except Exception as exc:  # noqa: BLE001
        _logger.warning("list_industry_names failed: %s", exc)
        return []


def enrich_empty_industries(rows: list[QuoteRow], mapping: dict[str, str]) -> int:
    count = 0
    for row in rows:
        if (row.industry or "").strip():
            continue
        industry = mapping.get(row.symbol)
        if not industry:
            continue
        row.industry = industry
        count += 1
    return count


def enrich_rows_from_db(db: Session | None, rows: list[QuoteRow]) -> int:
    if db is None:
        return 0
    return enrich_empty_industries(rows, load_industry_map(db))

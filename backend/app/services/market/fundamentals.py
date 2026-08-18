"""自选基本面只读：财报 snapshot + 披露日历。"""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.schemas.watchlist import DisclosureOut, FinancialSnapshotOut, FinancialSyncOut, FundamentalsOut
from app.services.market.bar_download import to_ts_code
from app.services.symbols import parse_flexible_symbol, to_vt_symbol

DISCLOSURE_LIMIT = 3


def get_fundamentals(db: Session, vt_symbol: str) -> FundamentalsOut:
    raw = (vt_symbol or "").strip()
    if not raw:
        raise HTTPException(status_code=400, detail="代码为空")
    try:
        symbol, exchange = parse_flexible_symbol(raw)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    vt = to_vt_symbol(symbol, exchange)
    ts = to_ts_code(symbol, exchange)

    snap = (
        db.execute(
            text(
                """
            SELECT end_date, revenue, net_income, revenue_yoy, net_income_yoy, roe, debt_ratio
            FROM app.financial_snapshots
            WHERE ts_code = :ts
            ORDER BY end_date DESC
            LIMIT 1
            """
            ),
            {"ts": ts},
        )
        .mappings()
        .first()
    )

    sync = (
        db.execute(
            text(
                """
            SELECT last_sync_at, latest_end_date, periods_count, sync_status, error_message
            FROM app.financial_sync_meta
            WHERE ts_code = :ts
            """
            ),
            {"ts": ts},
        )
        .mappings()
        .first()
    )

    discs = (
        db.execute(
            text(
                """
            SELECT end_date, pre_date, ann_date, actual_date
            FROM app.disclosure_calendar
            WHERE ts_code = :ts
            ORDER BY end_date DESC
            LIMIT :lim
            """
            ),
            {"ts": ts, "lim": DISCLOSURE_LIMIT},
        )
        .mappings()
        .all()
    )

    return FundamentalsOut(
        vt_symbol=vt,
        ts_code=ts,
        snapshot=FinancialSnapshotOut(**dict(snap)) if snap else None,
        sync=FinancialSyncOut(**dict(sync)) if sync else None,
        disclosures=[DisclosureOut(**dict(r)) for r in discs],
    )

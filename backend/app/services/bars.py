from __future__ import annotations

from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.bars import DbBarData
from app.schemas.watchlist import BarOut, BarsResponse
from app.services.symbols import normalize_exchange, to_vt_symbol


def load_bars(
    db: Session,
    *,
    symbol: str,
    exchange: str,
    interval: str = "d",
    limit: int = 120,
    end: datetime | None = None,
) -> BarsResponse:
    exch = normalize_exchange(exchange)
    interval = (interval or "d").strip().lower()
    if interval not in {"d", "1m", "5m", "15m", "30m", "1h"}:
        raise HTTPException(status_code=400, detail=f"不支持的周期：{interval}")
    limit = max(1, min(limit, 2000))

    stmt = (
        select(DbBarData)
        .where(
            DbBarData.symbol == symbol,
            DbBarData.exchange == exch,
            DbBarData.interval == interval,
        )
        .order_by(DbBarData.datetime.desc())
        .limit(limit)
    )
    if end is not None:
        stmt = stmt.where(DbBarData.datetime <= end)

    rows = list(db.scalars(stmt))
    rows.reverse()
    if not rows:
        raise HTTPException(status_code=404, detail="无 K 线数据，请先在 Ops 补全日 K 或使用 zak 下载")

    bars = [
        BarOut(
            datetime=row.datetime.isoformat(sep=" "),
            open=float(row.open_price or 0),
            high=float(row.high_price or 0),
            low=float(row.low_price or 0),
            close=float(row.close_price or 0),
            volume=float(row.volume or 0),
            turnover=float(row.turnover or 0),
        )
        for row in rows
    ]
    return BarsResponse(
        symbol=symbol,
        exchange=exch,
        vt_symbol=to_vt_symbol(symbol, exch),
        interval=interval,
        bars=bars,
    )

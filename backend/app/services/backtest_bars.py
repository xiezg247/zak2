"""日 K 加载与可序列化 bar 记录（不依赖 vnpy）。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.bars import DbBarData
from app.services.watchlist_repo import resolve_symbol_pair


@dataclass
class Bar:
    dt: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


def load_daily_bars(
    db: Session,
    *,
    vt_symbol: str,
    start_date: str,
    end_date: str,
    min_bars: int = 30,
) -> list[Bar]:
    symbol, exchange = resolve_symbol_pair(vt_symbol)
    try:
        start = datetime.fromisoformat(start_date[:10])
        end = datetime.fromisoformat(end_date[:10]).replace(hour=23, minute=59, second=59)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="日期格式须为 YYYY-MM-DD") from exc

    rows = list(
        db.scalars(
            select(DbBarData)
            .where(
                DbBarData.symbol == symbol,
                DbBarData.exchange == exchange,
                DbBarData.interval == "d",
                DbBarData.datetime >= start,
                DbBarData.datetime <= end,
            )
            .order_by(DbBarData.datetime)
        )
    )
    need = max(1, int(min_bars))
    if len(rows) < need:
        raise HTTPException(
            status_code=404,
            detail=f"日 K 不足（{len(rows)}，需要至少 {need} 根），请先在 Ops 补全日 K",
        )
    return [
        Bar(
            dt=r.datetime,
            open=float(r.open_price or 0),
            high=float(r.high_price or 0),
            low=float(r.low_price or 0),
            close=float(r.close_price or 0),
            volume=float(r.volume or 0),
        )
        for r in rows
        if (r.close_price or 0) > 0
    ]


def bars_to_records(bars: list[Bar]) -> list[dict]:
    """转为可 JSON 序列化的 OHLCV 记录，供子进程载荷。"""
    out: list[dict] = []
    for b in bars:
        out.append(
            {
                "datetime": b.dt.isoformat(),
                "open": b.open,
                "high": b.high,
                "low": b.low,
                "close": b.close,
                "volume": b.volume,
            }
        )
    return out

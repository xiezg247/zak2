"""K 线加载与可序列化 bar 记录（不依赖 vnpy）。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.bars import DbBarData
from app.repositories.watchlist import resolve_symbol_pair

ALLOWED_INTERVALS = frozenset({"d", "1m"})


@dataclass
class Bar:
    dt: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


def count_trading_days(bars: list[Bar]) -> int:
    return len({b.dt.date() for b in bars})


def load_bars(
    db: Session,
    *,
    vt_symbol: str,
    start_date: str,
    end_date: str,
    interval: str = "d",
    min_bars: int = 30,
    max_trading_days: int | None = None,
) -> list[Bar]:
    if interval not in ALLOWED_INTERVALS:
        raise HTTPException(status_code=400, detail=f"不支持的周期：{interval}")

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
                DbBarData.interval == interval,
                DbBarData.datetime >= start,
                DbBarData.datetime <= end,
            )
            .order_by(DbBarData.datetime)
        )
    )
    bars = [
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

    need = max(1, int(min_bars))
    if len(bars) < need:
        if interval == "1m":
            detail = (
                f"分钟 K 不足（{len(bars)}，需要至少 {need} 根），请先在 Ops 跑 fill_focus_pool_minute 补全关注池 1m"
            )
        else:
            detail = f"日 K 不足（{len(bars)}，需要至少 {need} 根），请先在 Ops 补全日 K"
        raise HTTPException(status_code=404, detail=detail)

    if interval == "1m" and max_trading_days is not None:
        days = count_trading_days(bars)
        limit = int(max_trading_days)
        if days > limit:
            raise HTTPException(
                status_code=400,
                detail=f"分钟回测交易日过多（{days} 天，上限 {limit}），请缩小日期区间",
            )

    return bars


def load_daily_bars(
    db: Session,
    *,
    vt_symbol: str,
    start_date: str,
    end_date: str,
    min_bars: int = 30,
) -> list[Bar]:
    return load_bars(
        db,
        vt_symbol=vt_symbol,
        start_date=start_date,
        end_date=end_date,
        interval="d",
        min_bars=min_bars,
    )


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

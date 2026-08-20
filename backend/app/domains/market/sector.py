"""板块资金（日频 / 盘中）。"""

from __future__ import annotations

from app.core.errors import ValidationFailed
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models.market import SectorFlowDaily, SectorFlowIntraday
from app.domains.market.schemas import SectorFlowRow, SectorIntradayPoint


def list_trade_dates(db: Session, *, limit: int = 30) -> list[str]:
    rows = db.scalars(
        select(SectorFlowDaily.trade_date).distinct().order_by(desc(SectorFlowDaily.trade_date)).limit(limit)
    )
    return list(rows)


def latest_trade_date(db: Session) -> str | None:
    dates = list_trade_dates(db, limit=1)
    return dates[0] if dates else None


def list_sector_flow(
    db: Session,
    *,
    kind: str = "industry",
    trade_date: str | None = None,
    sort: str = "net_flow_yi",
    limit: int = 50,
) -> list[SectorFlowRow]:
    kind = kind.strip().lower()
    if kind not in {"industry", "concept"}:
        raise ValidationFailed("kind 须为 industry 或 concept")
    sort = sort.strip()
    if sort not in {"net_flow_yi", "change_pct"}:
        raise ValidationFailed("sort 须为 net_flow_yi 或 change_pct")

    date = trade_date or latest_trade_date(db)
    if not date:
        return []

    order_col = SectorFlowDaily.net_flow_yi if sort == "net_flow_yi" else SectorFlowDaily.change_pct
    rows = db.scalars(
        select(SectorFlowDaily)
        .where(SectorFlowDaily.trade_date == date, SectorFlowDaily.sector_kind == kind)
        .order_by(desc(order_col))
        .limit(max(1, min(limit, 200)))
    )
    return [
        SectorFlowRow(
            trade_date=r.trade_date,
            sector_kind=r.sector_kind,
            sector_id=r.sector_id,
            name=r.name,
            change_pct=float(r.change_pct),
            net_flow_yi=float(r.net_flow_yi),
            flow_source=r.flow_source or "",
        )
        for r in rows
    ]


def sector_intraday(
    db: Session,
    *,
    sector_id: str,
    kind: str = "industry",
    trade_date: str | None = None,
) -> list[SectorIntradayPoint]:
    date = trade_date
    if not date:
        row = db.scalar(
            select(SectorFlowIntraday.trade_date)
            .where(SectorFlowIntraday.sector_id == sector_id, SectorFlowIntraday.sector_kind == kind)
            .order_by(desc(SectorFlowIntraday.trade_date))
            .limit(1)
        )
        date = row
    if not date:
        return []
    rows = db.scalars(
        select(SectorFlowIntraday)
        .where(
            SectorFlowIntraday.trade_date == date,
            SectorFlowIntraday.sector_kind == kind,
            SectorFlowIntraday.sector_id == sector_id,
        )
        .order_by(SectorFlowIntraday.clock_minutes)
    )
    return [
        SectorIntradayPoint(
            bucket_time=r.bucket_time,
            clock_minutes=r.clock_minutes,
            net_flow_yi=float(r.net_flow_yi),
            change_pct=float(r.change_pct),
        )
        for r in rows
    ]

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.time import china_today
from app.models.content import DisciplineDaily, PlaybookSection
from app.schemas.content import DisciplineCheckOut, PlaybookSectionOut, PlaybookSectionUpdate

DEFAULT_DISCIPLINE_CHECKS: tuple[tuple[str, str], ...] = (
    ("no_off_plan", "不在计划外开新仓"),
    ("morning_exit", "11:30 前评估上午必卖"),
    ("recession_flat", "退潮期不新开仓"),
    ("stop_first", "止损铁则优先于「再等等」"),
    ("no_intraday_rule_change", "盘中不改规则，复盘后再改"),
)


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def list_sections(db: Session) -> list[PlaybookSectionOut]:
    rows = db.scalars(select(PlaybookSection).order_by(PlaybookSection.sort_order, PlaybookSection.section_id))
    return [
        PlaybookSectionOut(
            section_id=r.section_id,
            title=r.title,
            body_md=r.body_md or "",
            collapsed=bool(r.collapsed),
            sort_order=r.sort_order,
            updated_at=r.updated_at,
        )
        for r in rows
    ]


def update_section(db: Session, section_id: str, body: PlaybookSectionUpdate) -> PlaybookSectionOut:
    row = db.scalar(select(PlaybookSection).where(PlaybookSection.section_id == section_id))
    if not row:
        raise HTTPException(status_code=404, detail="章节不存在")
    if body.title is not None:
        row.title = body.title
    if body.body_md is not None:
        row.body_md = body.body_md
    if body.collapsed is not None:
        row.collapsed = 1 if body.collapsed else 0
    row.updated_at = _now()
    db.commit()
    db.refresh(row)
    return PlaybookSectionOut(
        section_id=row.section_id,
        title=row.title,
        body_md=row.body_md or "",
        collapsed=bool(row.collapsed),
        sort_order=row.sort_order,
        updated_at=row.updated_at,
    )


def list_discipline(db: Session, user_id: str, trade_date: str | None = None) -> list[DisciplineCheckOut]:
    day = (trade_date or china_today().isoformat())[:10]
    rows = db.scalars(
        select(DisciplineDaily).where(DisciplineDaily.user_id == user_id, DisciplineDaily.trade_date == day)
    )
    checked_map = {r.check_id: bool(r.checked) for r in rows}
    return [
        DisciplineCheckOut(check_id=cid, label=label, checked=checked_map.get(cid, False))
        for cid, label in DEFAULT_DISCIPLINE_CHECKS
    ]


def set_discipline(
    db: Session, user_id: str, check_id: str, checked: bool, trade_date: str | None = None
) -> DisciplineCheckOut:
    labels = dict(DEFAULT_DISCIPLINE_CHECKS)
    if check_id not in labels:
        raise HTTPException(status_code=400, detail="未知检查项")
    day = (trade_date or china_today().isoformat())[:10]
    row = db.scalar(
        select(DisciplineDaily).where(
            DisciplineDaily.user_id == user_id,
            DisciplineDaily.trade_date == day,
            DisciplineDaily.check_id == check_id,
        )
    )
    if row:
        row.checked = 1 if checked else 0
    else:
        row = DisciplineDaily(user_id=user_id, trade_date=day, check_id=check_id, checked=1 if checked else 0)
        db.add(row)
    db.commit()
    return DisciplineCheckOut(check_id=check_id, label=labels[check_id], checked=checked)

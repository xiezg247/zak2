"""交易计划激活 / 废弃 / 轻编辑。"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.content import TradingPlan, TradingPlanSymbol
from app.schemas.content import PlanOut
from app.services.feed import plan_to_out

MAX_PLAN_SYMBOLS = 20


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def get_user_plan(db: Session, user_id: str, plan_id: str) -> TradingPlan:
    plan = db.scalar(
        select(TradingPlan).where(TradingPlan.id == plan_id, TradingPlan.user_id == user_id)
    )
    if plan is None:
        raise HTTPException(status_code=404, detail="计划不存在")
    return plan


def load_plan_out(db: Session, user_id: str, plan: TradingPlan) -> PlanOut:
    syms = list(
        db.scalars(
            select(TradingPlanSymbol)
            .where(TradingPlanSymbol.plan_id == plan.id, TradingPlanSymbol.user_id == user_id)
            .order_by(TradingPlanSymbol.sort_order)
        )
    )
    return plan_to_out(plan, syms)


def activate_plan(db: Session, user_id: str, plan_id: str) -> PlanOut:
    plan = get_user_plan(db, user_id, plan_id)
    if plan.status == "active":
        return load_plan_out(db, user_id, plan)
    if plan.status not in {"draft", "abandoned"}:
        raise HTTPException(status_code=400, detail=f"无法激活状态「{plan.status}」")
    now = _now()
    others = list(
        db.scalars(
            select(TradingPlan).where(
                TradingPlan.user_id == user_id,
                TradingPlan.trade_date == plan.trade_date,
                TradingPlan.status == "active",
                TradingPlan.id != plan.id,
            )
        )
    )
    for o in others:
        o.status = "abandoned"
        o.updated_at = now
    plan.status = "active"
    plan.updated_at = now
    db.commit()
    db.refresh(plan)
    return load_plan_out(db, user_id, plan)


def abandon_plan(db: Session, user_id: str, plan_id: str) -> PlanOut:
    plan = get_user_plan(db, user_id, plan_id)
    if plan.status != "abandoned":
        plan.status = "abandoned"
        plan.updated_at = _now()
        db.commit()
        db.refresh(plan)
    return load_plan_out(db, user_id, plan)

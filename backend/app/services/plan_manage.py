"""交易计划激活 / 废弃 / 轻编辑。"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.content import TradingPlan, TradingPlanSymbol
from app.schemas.content import PlanOut
from app.services.feed import plan_to_out
from app.services.symbols import parse_flexible_symbol, to_vt_symbol
from app.services.trading_risk import normalize_plan_max_pct

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


def _normalize_max_pct(raw: float) -> float:
    n = normalize_plan_max_pct(float(raw))
    if n is None or n <= 0 or n > 1:
        raise HTTPException(status_code=400, detail="仓位上限须在 (0, 100%]（或 0–1 小数）")
    return n


def _replace_symbols(db: Session, user_id: str, plan: TradingPlan, raw_list: list[str]) -> None:
    if len(raw_list) > MAX_PLAN_SYMBOLS:
        raise HTTPException(status_code=400, detail=f"标的最多 {MAX_PLAN_SYMBOLS} 只")
    parsed: list[tuple[str, str]] = []
    seen: set[str] = set()
    for raw in raw_list:
        try:
            code, exch = parse_flexible_symbol(raw)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        vt = to_vt_symbol(code, exch)
        if vt in seen:
            continue
        seen.add(vt)
        parsed.append((code, exch))
    db.execute(
        delete(TradingPlanSymbol).where(
            TradingPlanSymbol.plan_id == plan.id,
            TradingPlanSymbol.user_id == user_id,
        )
    )
    for i, (code, exch) in enumerate(parsed):
        db.add(
            TradingPlanSymbol(
                plan_id=plan.id,
                symbol=code,
                exchange=exch,
                user_id=user_id,
                allowed_modes="",
                entry_conditions="",
                exit_conditions="",
                sort_order=i,
            )
        )


def update_plan(
    db: Session,
    user_id: str,
    plan_id: str,
    *,
    notes: str | None = None,
    max_position_pct: float | None = None,
    symbols: list[str] | None = None,
) -> PlanOut:
    plan = get_user_plan(db, user_id, plan_id)
    if plan.status == "abandoned":
        raise HTTPException(status_code=403, detail="已废弃计划不可编辑")
    if notes is None and max_position_pct is None and symbols is None:
        raise HTTPException(status_code=400, detail="请至少提供 notes / max_position_pct / symbols 之一")
    if notes is not None:
        plan.notes = notes
    if max_position_pct is not None:
        plan.max_position_pct = _normalize_max_pct(max_position_pct)
    if symbols is not None:
        _replace_symbols(db, user_id, plan, symbols)
    plan.updated_at = _now()
    db.commit()
    db.refresh(plan)
    return load_plan_out(db, user_id, plan)

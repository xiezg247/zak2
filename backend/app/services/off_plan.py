"""计划外持仓判定：对比当日 active 计划标的与持仓 vt_symbol。"""

from __future__ import annotations

from typing import Any, cast

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models.content import TradingPlan, TradingPlanSymbol
from app.services.symbols import to_vt_symbol


def load_active_plan_snapshot(
    db: Session,
    user_id: str,
    trade_date: str,
) -> dict[str, Any] | None:
    """返回当日 active 计划快照；无计划则 None。

    形如 ``{"vt_symbols": set[str], "ordered_vt_symbols": list[str], "max_position_pct": float, "trade_date": str}``。
    """
    plan = db.scalar(
        select(TradingPlan)
        .where(
            TradingPlan.user_id == user_id,
            TradingPlan.trade_date == trade_date,
            TradingPlan.status == "active",
        )
        .order_by(desc(TradingPlan.updated_at))
        .limit(1)
    )
    if plan is None:
        return None
    symbols = list(
        db.scalars(
            select(TradingPlanSymbol)
            .where(
                TradingPlanSymbol.plan_id == plan.id,
                TradingPlanSymbol.user_id == user_id,
            )
            .order_by(TradingPlanSymbol.sort_order)
        )
    )
    ordered: list[str] = []
    seen: set[str] = set()
    for s in symbols:
        vt = to_vt_symbol(s.symbol, s.exchange)
        if vt in seen:
            continue
        seen.add(vt)
        ordered.append(vt)
    return {
        "vt_symbols": set(ordered),
        "ordered_vt_symbols": ordered,
        "max_position_pct": float(plan.max_position_pct or 0),
        "trade_date": str(plan.trade_date or trade_date),
    }


def load_active_plan_vt_symbols(
    db: Session,
    user_id: str,
    trade_date: str,
) -> set[str] | None:
    snap = load_active_plan_snapshot(db, user_id, trade_date)
    if snap is None:
        return None
    return cast(set[str], snap["vt_symbols"])


def list_off_plan_vt_symbols(
    position_vts: list[str],
    plan_vts: set[str] | None,
) -> list[str]:
    if plan_vts is None:
        return []
    return [vt for vt in position_vts if vt not in plan_vts]


def build_plan_symbol_statuses(
    *,
    ordered_vt_symbols: list[str],
    watchlist_vts: set[str],
    position_vts: set[str],
    name_by_vt: dict[str, str],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for vt in ordered_vt_symbols:
        out.append(
            {
                "vt_symbol": vt,
                "name": name_by_vt.get(vt, "") or "",
                "in_watchlist": vt in watchlist_vts,
                "in_position": vt in position_vts,
            }
        )
    return out

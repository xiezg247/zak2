"""雷达共振 → 次日 trading_plans draft。"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime

from fastapi import HTTPException
from sqlalchemy import delete, desc, select, text
from sqlalchemy.orm import Session

from app.core.time import china_today
from app.models.content import TradingPlan, TradingPlanSymbol
from app.services.emotion_cycle import build_emotion_cycle
from app.services.plan_manage import MAX_PLAN_SYMBOLS
from app.services.radar import list_radar_cards
from app.services.radar_resonance import list_radar_resonance
from app.services.symbols import parse_flexible_symbol, to_vt_symbol
from app.services.tushare_screener import latest_open_yyyymmdd

DEFAULT_PLAN_MAX_POSITION_PCT = 0.3


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def clamp_top_n(n: int | None) -> int:
    if n is None:
        return 5
    return max(3, min(8, n))


def normalize_trade_date(raw: str | None) -> str | None:
    if raw is None:
        return None
    s = str(raw).strip()
    if len(s) == 8 and s.isdigit():
        return f"{s[:4]}-{s[4:6]}-{s[6:8]}"
    if len(s) == 10 and s[4] == "-" and s[7] == "-":
        ymd = s.replace("-", "")
        if len(ymd) == 8 and ymd.isdigit():
            return s
    return None


def resolve_next_trade_date(db: Session, *, today: date | None = None) -> tuple[str, bool]:
    ref = today or china_today()
    ymd = ref.strftime("%Y%m%d")
    cal = db.execute(
        text(
            """
            SELECT cal_date FROM app.trade_calendar
            WHERE is_open = 1
              AND REPLACE(cal_date, '-', '') > :ymd
            ORDER BY REPLACE(cal_date, '-', '') ASC
            LIMIT 1
            """
        ),
        {"ymd": ymd},
    ).scalar()
    if cal:
        normalized = normalize_trade_date(str(cal))
        if normalized:
            return normalized, False
    fallback = latest_open_yyyymmdd(db)
    normalized = normalize_trade_date(fallback)
    if normalized:
        return normalized, True
    return ref.strftime("%Y-%m-%d"), True


def create_resonance_plan_draft(
    db: Session,
    user_id: str,
    *,
    top_n: int | None = None,
    trade_date: str | None = None,
) -> dict:
    cycle = build_emotion_cycle(db)
    stage = str(cycle.get("stage") or "")
    stage_label = str(cycle.get("stage_label") or stage)
    if stage in {"ice", "recession"}:
        raise HTTPException(status_code=400, detail="当前情绪不宜新开（冰点/退潮）")

    cards = list_radar_cards(db)
    if not cards:
        raise HTTPException(status_code=400, detail="暂无雷达卡片，请先打开雷达页刷新")

    n = clamp_top_n(top_n)
    resonance = list_radar_resonance(db, user_id=user_id, min_cards=2, top_n=n)
    if not resonance.entries:
        raise HTTPException(status_code=400, detail="暂无共振标的")

    calendar_fallback = False
    if trade_date:
        td = normalize_trade_date(trade_date)
        if not td:
            raise HTTPException(status_code=400, detail="trade_date 格式无效")
    else:
        td, calendar_fallback = resolve_next_trade_date(db)

    now = _now()
    existing = db.scalar(
        select(TradingPlan)
        .where(
            TradingPlan.user_id == user_id,
            TradingPlan.trade_date == td,
            TradingPlan.status == "draft",
        )
        .order_by(desc(TradingPlan.updated_at))
        .limit(1)
    )
    replaced = existing is not None

    notes = f"雷达共振草案 · 情绪{stage_label} · top_n={n}"
    if calendar_fallback:
        notes += " · 日历缺省用最近开市日"

    if existing:
        plan = existing
        db.execute(
            delete(TradingPlanSymbol).where(
                TradingPlanSymbol.plan_id == plan.id,
                TradingPlanSymbol.user_id == user_id,
            )
        )
        db.flush()
        plan.emotion_expected = stage
        plan.max_position_pct = DEFAULT_PLAN_MAX_POSITION_PCT
        plan.notes = notes
        plan.updated_at = now
    else:
        plan = TradingPlan(
            id=uuid.uuid4().hex,
            user_id=user_id,
            trade_date=td,
            emotion_expected=stage,
            max_position_pct=DEFAULT_PLAN_MAX_POSITION_PCT,
            notes=notes,
            status="draft",
            created_at=now,
            updated_at=now,
        )
        db.add(plan)

    symbols_out: list[dict[str, str]] = []
    for idx, entry in enumerate(resonance.entries):
        code, exch = parse_flexible_symbol(entry.vt_symbol)
        titles = "、".join(entry.card_titles) if entry.card_titles else f"{entry.card_count}卡"
        entry_cond = f"共振 加权{entry.resonance_score:g}：{titles}"
        db.add(
            TradingPlanSymbol(
                plan_id=plan.id,
                symbol=code,
                exchange=exch,
                user_id=user_id,
                allowed_modes="",
                entry_conditions=entry_cond,
                exit_conditions="",
                sort_order=idx,
            )
        )
        symbols_out.append({"vt_symbol": entry.vt_symbol, "name": entry.name or ""})

    db.commit()
    return {
        "plan_id": plan.id,
        "trade_date": td,
        "status": "draft",
        "emotion_expected": stage,
        "symbol_count": len(symbols_out),
        "symbols": symbols_out,
        "replaced": replaced,
    }


def append_symbol_to_draft(
    db: Session,
    user_id: str,
    *,
    vt_symbol: str,
    name: str | None = None,
    source: str | None = None,
) -> dict:
    """确保次一交易日 draft 存在并追加一标的（不因情绪拒建）。"""
    _ = name
    try:
        code, exch = parse_flexible_symbol(vt_symbol)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    vt = to_vt_symbol(code, exch)
    td, _ = resolve_next_trade_date(db)
    now = _now()

    plan = db.scalar(
        select(TradingPlan)
        .where(
            TradingPlan.user_id == user_id,
            TradingPlan.trade_date == td,
            TradingPlan.status == "draft",
        )
        .order_by(desc(TradingPlan.updated_at))
        .limit(1)
    )
    if plan is None:
        plan = TradingPlan(
            id=uuid.uuid4().hex,
            user_id=user_id,
            trade_date=td,
            emotion_expected="",
            max_position_pct=DEFAULT_PLAN_MAX_POSITION_PCT,
            notes="展望行追加",
            status="draft",
            created_at=now,
            updated_at=now,
        )
        db.add(plan)
        db.flush()

    existing = list(
        db.scalars(
            select(TradingPlanSymbol)
            .where(
                TradingPlanSymbol.plan_id == plan.id,
                TradingPlanSymbol.user_id == user_id,
            )
            .order_by(TradingPlanSymbol.sort_order)
        )
    )
    vts = [to_vt_symbol(s.symbol, s.exchange) for s in existing]
    if vt in vts:
        return {
            "added": False,
            "plan_id": plan.id,
            "trade_date": td,
            "symbol_count": len(vts),
            "status": "draft",
            "message": f"已在草案 {vt}",
        }
    if len(vts) >= MAX_PLAN_SYMBOLS:
        raise HTTPException(status_code=400, detail=f"标的最多 {MAX_PLAN_SYMBOLS} 只")

    entry = ""
    if source == "predict":
        entry = "来自规则预测"
    elif source == "horizon":
        entry = "来自共振展望"

    db.add(
        TradingPlanSymbol(
            plan_id=plan.id,
            symbol=code,
            exchange=exch,
            user_id=user_id,
            allowed_modes="",
            entry_conditions=entry,
            exit_conditions="",
            sort_order=len(existing),
        )
    )
    plan.updated_at = now
    db.commit()
    return {
        "added": True,
        "plan_id": plan.id,
        "trade_date": td,
        "symbol_count": len(vts) + 1,
        "status": "draft",
        "message": f"已加入草案 {vt}",
    }

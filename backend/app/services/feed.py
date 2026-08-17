from __future__ import annotations

import json
import logging
import uuid
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import delete, desc, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.settings import get_settings
from app.integrations.bilibili.client import BilibiliApiError, BilibiliClient
from app.integrations.bilibili.user import get_user_profile, search_users
from app.models.content import FeedItem, FeedItemRead, FeedSubscription, TradingPlan, TradingPlanSymbol
from app.schemas.content import FeedItemOut, FeedSubOut, PlanOut
from app.services.ops.sync_bilibili_feed import SOURCE_TYPE, sync_one_subscription
from app.services.symbols import to_vt_symbol

logger = logging.getLogger(__name__)

MAX_FEED_SUBSCRIPTIONS = 50


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _sub_out(row: FeedSubscription, *, sync_error: str | None = None) -> FeedSubOut:
    return FeedSubOut(
        id=row.id,
        source_type=row.source_type,
        source_id=row.source_id,
        display_name=row.display_name,
        avatar_url=row.avatar_url,
        enabled=bool(row.enabled),
        sort_order=row.sort_order,
        sync_error=sync_error,
    )


def list_subscriptions(db: Session, user_id: str) -> list[FeedSubOut]:
    rows = db.scalars(
        select(FeedSubscription)
        .where(FeedSubscription.user_id == user_id)
        .order_by(FeedSubscription.sort_order, FeedSubscription.display_name)
    )
    return [_sub_out(r) for r in rows]


def set_subscription_enabled(db: Session, user_id: str, sub_id: str, enabled: bool) -> FeedSubOut:
    row = db.scalar(
        select(FeedSubscription).where(FeedSubscription.id == sub_id, FeedSubscription.user_id == user_id)
    )
    if not row:
        raise HTTPException(status_code=404, detail="订阅不存在")
    row.enabled = 1 if enabled else 0
    row.updated_at = _now()
    db.commit()
    db.refresh(row)
    return _sub_out(row)


def search_bilibili_ups(q: str, *, limit: int = 8) -> list[dict[str, str]]:
    cookies = (get_settings().bilibili_cookies or "").strip()
    if not cookies:
        raise HTTPException(status_code=400, detail="未配置 BILIBILI_COOKIES")
    limit = max(1, min(20, int(limit)))
    q = str(q or "").strip()
    if not q:
        return []
    client = BilibiliClient(cookies=cookies)
    try:
        try:
            return search_users(client, q, limit=limit)
        except BilibiliApiError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
    finally:
        client.close()


def add_bilibili_up(
    db: Session,
    user_id: str,
    mid: str,
    *,
    sync_now: bool = False,
) -> FeedSubOut:
    cookies = (get_settings().bilibili_cookies or "").strip()
    if not cookies:
        raise HTTPException(status_code=400, detail="未配置 BILIBILI_COOKIES")

    mid = str(mid).strip()
    if not mid or not mid.isdigit():
        raise HTTPException(status_code=400, detail="mid 无效")

    count = db.scalar(
        select(func.count())
        .select_from(FeedSubscription)
        .where(FeedSubscription.user_id == user_id)
    )
    if int(count or 0) >= MAX_FEED_SUBSCRIPTIONS:
        raise HTTPException(status_code=400, detail="订阅数已达上限")

    existing = db.scalar(
        select(FeedSubscription).where(
            FeedSubscription.user_id == user_id,
            FeedSubscription.source_type == SOURCE_TYPE,
            FeedSubscription.source_id == mid,
        )
    )
    if existing:
        raise HTTPException(status_code=400, detail="已订阅该 UP")

    display_name = mid
    avatar_url = ""
    client = BilibiliClient(cookies=cookies)
    try:
        try:
            profile = get_user_profile(client, mid)
            display_name = profile.get("name") or mid
            avatar_url = profile.get("avatar") or ""
        except Exception:  # noqa: BLE001 — profile 失败仍创建
            logger.warning("获取 UP 资料失败，仍创建订阅: mid=%s", mid)

        now = _now()
        row = FeedSubscription(
            id=str(uuid.uuid4()),
            user_id=user_id,
            source_type=SOURCE_TYPE,
            source_id=mid,
            display_name=display_name,
            avatar_url=avatar_url,
            config_json=json.dumps({}),
            enabled=1,
            sort_order=0,
            created_at=now,
            updated_at=now,
        )
        try:
            db.add(row)
            db.flush()
        except IntegrityError as exc:
            db.rollback()
            raise HTTPException(status_code=400, detail="该 UP 已被订阅") from exc

        sync_error: str | None = None
        if sync_now:
            try:
                sync_one_subscription(db, client, row)
            except Exception as exc:  # noqa: BLE001
                sync_error = str(exc)

        db.commit()
        db.refresh(row)
        return _sub_out(row, sync_error=sync_error)
    finally:
        client.close()


def delete_subscription(db: Session, user_id: str, sub_id: str) -> None:
    row = db.scalar(
        select(FeedSubscription).where(FeedSubscription.id == sub_id, FeedSubscription.user_id == user_id)
    )
    if not row:
        raise HTTPException(status_code=404, detail="订阅不存在")

    item_ids = list(db.scalars(select(FeedItem.id).where(FeedItem.subscription_id == sub_id)))
    if item_ids:
        db.execute(delete(FeedItemRead).where(FeedItemRead.item_id.in_(item_ids)))
    db.execute(delete(FeedItem).where(FeedItem.subscription_id == sub_id))
    db.execute(delete(FeedSubscription).where(FeedSubscription.id == sub_id))
    db.commit()


def list_feed_items(
    db: Session,
    user_id: str,
    *,
    subscription_id: str | None = None,
    limit: int = 50,
) -> list[FeedItemOut]:
    subs = list_subscriptions(db, user_id)
    sub_ids = {s.id for s in subs if s.enabled or subscription_id}
    if subscription_id:
        if subscription_id not in {s.id for s in subs}:
            raise HTTPException(status_code=404, detail="订阅不存在")
        sub_ids = {subscription_id}
    if not sub_ids:
        return []

    rows = list(
        db.scalars(
            select(FeedItem)
            .where(FeedItem.subscription_id.in_(sub_ids))
            .order_by(desc(FeedItem.published_at), desc(FeedItem.created_at))
            .limit(max(1, min(limit, 200)))
        )
    )
    reads = {
        r.item_id
        for r in db.scalars(
            select(FeedItemRead).where(
                FeedItemRead.user_id == user_id,
                FeedItemRead.item_id.in_([x.id for x in rows]),
            )
        )
    }
    return [
        FeedItemOut(
            id=r.id,
            subscription_id=r.subscription_id,
            source_type=r.source_type,
            item_type=r.item_type,
            title=r.title or "",
            summary=r.summary or "",
            url=r.url,
            author_name=r.author_name or "",
            published_at=r.published_at,
            is_read=r.id in reads or bool(r.read_at),
        )
        for r in rows
    ]


def mark_feed_read(db: Session, user_id: str, item_id: str) -> dict:
    item = db.scalar(select(FeedItem).where(FeedItem.id == item_id))
    if not item:
        raise HTTPException(status_code=404, detail="动态不存在")
    # ensure belongs to user subscription
    sub = db.scalar(
        select(FeedSubscription).where(
            FeedSubscription.id == item.subscription_id,
            FeedSubscription.user_id == user_id,
        )
    )
    if not sub:
        raise HTTPException(status_code=404, detail="动态不存在")
    existing = db.scalar(
        select(FeedItemRead).where(FeedItemRead.user_id == user_id, FeedItemRead.item_id == item_id)
    )
    if not existing:
        db.add(FeedItemRead(user_id=user_id, item_id=item_id, read_at=_now()))
        db.commit()
    return {"ok": True}


def plan_to_out(plan: TradingPlan, symbols: list[TradingPlanSymbol]) -> PlanOut:
    return PlanOut(
        id=plan.id,
        trade_date=plan.trade_date,
        emotion_expected=plan.emotion_expected or "",
        max_position_pct=float(plan.max_position_pct or 0),
        notes=plan.notes or "",
        status=plan.status,
        symbols=[
            {
                "symbol": s.symbol,
                "exchange": s.exchange,
                "vt_symbol": to_vt_symbol(s.symbol, s.exchange),
                "allowed_modes": s.allowed_modes,
                "entry_conditions": s.entry_conditions,
                "exit_conditions": s.exit_conditions,
            }
            for s in symbols
        ],
    )


def list_plans(db: Session, user_id: str, *, limit: int = 20) -> list[PlanOut]:
    plans = list(
        db.scalars(
            select(TradingPlan)
            .where(TradingPlan.user_id == user_id)
            .order_by(desc(TradingPlan.trade_date), desc(TradingPlan.updated_at))
            .limit(limit)
        )
    )
    out: list[PlanOut] = []
    for p in plans:
        syms = list(
            db.scalars(
                select(TradingPlanSymbol)
                .where(TradingPlanSymbol.plan_id == p.id, TradingPlanSymbol.user_id == user_id)
                .order_by(TradingPlanSymbol.sort_order)
            )
        )
        out.append(plan_to_out(p, syms))
    return out

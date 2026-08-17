"""同步 B 站启用订阅动态 → feed_items。"""

from __future__ import annotations

import json
import time
import uuid
from datetime import UTC, datetime
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.settings import get_settings
from app.integrations.bilibili.client import BilibiliApiError, BilibiliClient
from app.integrations.bilibili.dynamics import list_recent_dynamics
from app.integrations.bilibili.normalize import normalize_dynamic
from app.models.content import FeedItem, FeedSubscription
from app.services.ops.scheduler import save_job_run_meta

JOB_ID = "sync_bilibili_feed"
FEED_RECENT_LIMIT = 10
SUBSCRIPTION_SLEEP_SEC = 2.0
SOURCE_TYPE = "bilibili_up"

_TZ = ZoneInfo("Asia/Shanghai")
_SYNC_START_HOUR = 8
_SYNC_END_HOUR = 20


def in_sync_window(now: datetime | None = None) -> bool:
    """是否在每日 08:00–20:00（Asia/Shanghai）同步窗口内（不含 20:00）。"""
    dt = now or datetime.now(_TZ)
    dt = dt.replace(tzinfo=_TZ) if dt.tzinfo is None else dt.astimezone(_TZ)
    return _SYNC_START_HOUR <= dt.hour < _SYNC_END_HOUR


def sync_bilibili_feed(db: Session, *, force: bool = False) -> dict[str, Any]:
    if not force and not in_sync_window():
        return _skip(db, "非 08:00–20:00 时段，已跳过 B 站订阅同步")

    cookies = (get_settings().bilibili_cookies or "").strip()
    if not cookies:
        return _skip(db, "未配置 BILIBILI_COOKIES，已跳过 B 站订阅同步")

    subs = list(
        db.scalars(
            select(FeedSubscription)
            .where(
                FeedSubscription.enabled == 1,
                FeedSubscription.source_type == SOURCE_TYPE,
            )
            .order_by(FeedSubscription.sort_order, FeedSubscription.display_name)
        )
    )
    if not subs:
        return _skip(db, "无启用的 B 站订阅，已跳过")

    client = BilibiliClient(cookies=cookies)
    new_items = 0
    errors: list[str] = []
    try:
        for index, sub in enumerate(subs):
            try:
                new_items += _sync_one_subscription(db, client, sub)
            except BilibiliApiError as exc:
                label = sub.display_name or sub.source_id
                errors.append(f"{label}: {exc}")
            except Exception as exc:
                label = sub.display_name or sub.source_id
                errors.append(f"{label}: {exc}")
            if index < len(subs) - 1:
                time.sleep(SUBSCRIPTION_SLEEP_SEC)
        db.commit()
    finally:
        client.close()

    success = len(errors) == 0
    if errors and new_items == 0:
        message = "；".join(errors[:3])
    else:
        message = f"同步完成：新增 {new_items} 条"
        if errors:
            message += f"；部分失败 {len(errors)} 个"

    save_job_run_meta(db, JOB_ID, last_message=message, last_success=success)
    out: dict[str, Any] = {
        "success": success,
        "message": message,
        "new_items": new_items,
    }
    if errors:
        out["errors"] = errors
    return out


def _skip(db: Session, message: str) -> dict[str, Any]:
    save_job_run_meta(db, JOB_ID, last_message=message, last_success=True)
    return {"success": True, "skipped": True, "message": message, "new_items": 0}


def _sync_one_subscription(db: Session, client: BilibiliClient, sub: FeedSubscription) -> int:
    raws = list_recent_dynamics(client, sub.source_id, count=FEED_RECENT_LIMIT)
    author = sub.display_name or sub.source_id
    created_at = datetime.now(UTC).isoformat(timespec="seconds")
    inserted = 0
    for raw in raws:
        draft = normalize_dynamic(raw, author_name=author)
        if draft is None:
            continue
        # DB UNIQUE(source_type, external_id) — match that key (not subscription_id).
        existing = db.scalar(
            select(FeedItem.id).where(
                FeedItem.source_type == sub.source_type,
                FeedItem.external_id == draft.external_id,
            )
        )
        if existing:
            continue
        try:
            # Savepoint: concurrent Ops+scheduler race must not roll back the batch.
            with db.begin_nested():
                db.add(
                    FeedItem(
                        id=str(uuid.uuid4()),
                        subscription_id=sub.id,
                        source_type=sub.source_type,
                        external_id=draft.external_id,
                        item_type=draft.item_type,
                        title=draft.title,
                        summary=draft.summary,
                        url=draft.url,
                        author_name=draft.author_name,
                        published_at=draft.published_at,
                        payload_json=json.dumps(draft.payload, ensure_ascii=False),
                        read_at=None,
                        created_at=created_at,
                    )
                )
                db.flush()
            inserted += 1
        except IntegrityError:
            continue
    return inserted


# 供 feed.add_bilibili_up(sync_now=True) 复用
sync_one_subscription = _sync_one_subscription

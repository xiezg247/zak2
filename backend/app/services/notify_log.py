"""通知投递历史只读查询（app.notify_delivery_log）。"""

from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.notify import NotifyDeliveryLog

DEFAULT_LIMIT = 50
MAX_LIMIT = 100


def clamp_limit(raw: int | None) -> int:
    if raw is None:
        return DEFAULT_LIMIT
    if raw <= 0:
        return 1
    if raw > MAX_LIMIT:
        return MAX_LIMIT
    return raw


def parse_payload(payload_json: str) -> dict:
    try:
        parsed = json.loads(payload_json)
        if isinstance(parsed, dict):
            return parsed
        return {"_raw": parsed}
    except (json.JSONDecodeError, TypeError, ValueError):
        return {"_raw": payload_json}


def list_notify_log(db: Session, user_id: str, *, limit: int | None = None) -> dict:
    lim = clamp_limit(limit)
    rows = db.scalars(
        select(NotifyDeliveryLog)
        .where(NotifyDeliveryLog.user_id == user_id)
        .order_by(NotifyDeliveryLog.created_at.desc())
        .limit(lim)
    )

    items = []
    for row in rows:
        payload_text = str(row.payload_json or "")
        items.append(
            {
                "id": str(row.id),
                "event_type": str(row.event_type),
                "channel": str(row.channel),
                "status": str(row.status),
                "error": str(row.error or ""),
                "created_at": str(row.created_at),
                "payload": parse_payload(payload_text),
            }
        )

    return {"items": items, "limit": lim, "count": len(items)}

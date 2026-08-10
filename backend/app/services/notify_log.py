"""通知投递历史只读查询（app.notify_delivery_log）。"""

from __future__ import annotations

import json

from sqlalchemy import text
from sqlalchemy.orm import Session

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
    rows = db.execute(
        text(
            """
            SELECT id, event_type, channel, payload_json, status, error, created_at
            FROM app.notify_delivery_log
            WHERE user_id = CAST(:uid AS uuid)
            ORDER BY created_at DESC
            LIMIT :lim
            """
        ),
        {"uid": user_id, "lim": lim},
    ).mappings().all()

    items = []
    for row in rows:
        raw_payload = row.get("payload_json")
        payload_text = "" if raw_payload is None else str(raw_payload)
        items.append(
            {
                "id": str(row["id"]),
                "event_type": str(row["event_type"]),
                "channel": str(row["channel"]),
                "status": str(row["status"]),
                "error": str(row.get("error") or ""),
                "created_at": str(row["created_at"]),
                "payload": parse_payload(payload_text),
            }
        )

    return {"items": items, "limit": lim, "count": len(items)}

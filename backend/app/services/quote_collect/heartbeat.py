"""采集进程心跳。"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

HEARTBEAT_KEY = "zak2:collector:heartbeat"
HEARTBEAT_TTL = 120
HEARTBEAT_FRESH_SEC = 90


def write_heartbeat(client: Any, payload: dict[str, Any]) -> None:
    body = dict(payload)
    if "ts" not in body:
        body["ts"] = datetime.now(timezone.utc).isoformat()
    client.set(HEARTBEAT_KEY, json.dumps(body, ensure_ascii=False), ex=HEARTBEAT_TTL)


def read_heartbeat(client: Any) -> dict[str, Any] | None:
    raw = client.get(HEARTBEAT_KEY)
    if not raw:
        return None
    text = raw.decode("utf-8") if isinstance(raw, bytes) else str(raw)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def is_heartbeat_fresh(payload: dict[str, Any] | None, *, now: datetime | None = None) -> bool:
    if not payload:
        return False
    ts_raw = payload.get("ts")
    if not ts_raw:
        return False
    try:
        ts = datetime.fromisoformat(str(ts_raw).replace("Z", "+00:00"))
    except ValueError:
        return False
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    ref = now or datetime.now(timezone.utc)
    if ref.tzinfo is None:
        ref = ref.replace(tzinfo=timezone.utc)
    return (ref - ts).total_seconds() < HEARTBEAT_FRESH_SEC

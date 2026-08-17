"""采集控制：force 命令 + Ops 封装。"""

from __future__ import annotations

from contextlib import suppress
from typing import Any

import redis

from app.core.settings import get_settings
from app.services.quote_collect.heartbeat import is_heartbeat_fresh, read_heartbeat

CMD_CHANNEL = "zak2:collector:cmd"


def publish_force(client: Any) -> None:
    client.publish(CMD_CHANNEL, "force")


def force_collect(client: Any) -> dict[str, Any]:
    hb = read_heartbeat(client)
    if not is_heartbeat_fresh(hb):
        return {
            "success": False,
            "message": "行情采集进程未运行，请启动：python -m app.quote_collector",
        }
    publish_force(client)
    return {"success": True, "message": "已发送强制采集命令"}


def collector_health(client: Any | None = None) -> dict[str, Any]:
    own = False
    if client is None:
        try:
            client = redis.Redis.from_url(get_settings().redis_url, decode_responses=True)
            own = True
            client.ping()
        except redis.RedisError:
            return {
                "running": False,
                "provider": None,
                "status": None,
                "last_count": 0,
                "ts": None,
                "hint": "Redis 不可用；请启动：python -m app.quote_collector",
            }
    try:
        hb = read_heartbeat(client)
        running = is_heartbeat_fresh(hb)
        if not hb:
            return {
                "running": False,
                "provider": None,
                "status": None,
                "last_count": 0,
                "ts": None,
                "hint": "请启动：python -m app.quote_collector",
            }
        return {
            "running": running,
            "provider": hb.get("provider"),
            "status": hb.get("status"),
            "last_count": int(hb.get("last_count") or 0),
            "ts": hb.get("ts"),
            "hint": None
            if running
            else "心跳过期；请启动：python -m app.quote_collector",
        }
    finally:
        if own and client is not None:
            with suppress(Exception):
                client.close()


def force_collect_from_settings() -> dict[str, Any]:
    try:
        client = redis.Redis.from_url(get_settings().redis_url, decode_responses=True)
        client.ping()
    except redis.RedisError:
        return {
            "success": False,
            "message": "Redis 不可用，无法发送强制采集命令",
        }
    try:
        return force_collect(client)
    finally:
        with suppress(Exception):
            client.close()

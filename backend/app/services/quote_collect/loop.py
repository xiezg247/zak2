"""采集一轮 / 常驻循环。"""

from __future__ import annotations

import logging
import os
import threading
import time
from datetime import datetime
from typing import Any

import redis
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.core.settings import get_settings
from app.services.quote_collect.control import CMD_CHANNEL
from app.services.quote_collect.heartbeat import write_heartbeat
from app.services.quote_collect.models import QuoteSnapshot
from app.services.quote_collect.provider import QuoteProvider, TickFlowProvider
from app.services.quote_collect.session import is_ashare_trading_session
from app.services.quote_collect.universe import load_tf_symbols
from app.services.quote_collect.writer import RedisQuoteWriter

logger = logging.getLogger(__name__)


def _clamp_interval(raw: int) -> int:
    return max(5, min(300, int(raw)))


def collect_once(
    *,
    db: Session,
    writer: RedisQuoteWriter,
    provider: QuoteProvider,
    client: Any,
    force: bool = False,
    now: datetime | None = None,
    interval_sec: int = 30,
    pid: int | None = None,
) -> dict[str, Any]:
    raw_name = getattr(provider, "name", "unknown")
    provider_name = raw_name if isinstance(raw_name, str) and raw_name else "unknown"
    base_hb: dict[str, Any] = {
        "pid": int(pid if pid is not None else os.getpid()),
        "provider": provider_name,
        "interval_sec": _clamp_interval(interval_sec),
        "last_count": 0,
        "last_duration_ms": 0,
        "last_error": "",
    }

    if not force and not is_ashare_trading_session(now):
        write_heartbeat(client, {**base_hb, "status": "skipped"})
        return {
            "success": True,
            "skipped": True,
            "message": "非交易时段，已跳过",
            "count": 0,
        }

    symbols = load_tf_symbols(db)
    if not symbols:
        write_heartbeat(client, {**base_hb, "status": "skipped", "last_error": "universe empty"})
        return {
            "success": True,
            "skipped": True,
            "message": "universe 为空，请先 sync_universe",
            "count": 0,
        }

    write_heartbeat(client, {**base_hb, "status": "collecting"})
    started = time.perf_counter()
    try:
        quotes: dict[str, QuoteSnapshot] = provider.fetch(symbols)
        count = writer.write_quotes(quotes)
        duration_ms = int((time.perf_counter() - started) * 1000)
        write_heartbeat(
            client,
            {
                **base_hb,
                "status": "idle",
                "last_count": count,
                "last_duration_ms": duration_ms,
            },
        )
        return {
            "success": True,
            "skipped": False,
            "message": f"写入 {count} 条行情",
            "count": count,
        }
    except Exception as exc:
        duration_ms = int((time.perf_counter() - started) * 1000)
        logger.exception("collect_once failed")
        write_heartbeat(
            client,
            {
                **base_hb,
                "status": "error",
                "last_duration_ms": duration_ms,
                "last_error": str(exc)[:500],
            },
        )
        return {
            "success": False,
            "skipped": False,
            "message": str(exc),
            "count": 0,
        }


def _listen_force(client: Any, force_event: threading.Event, stop: threading.Event) -> None:
    pubsub = client.pubsub(ignore_subscribe_messages=True)
    try:
        pubsub.subscribe(CMD_CHANNEL)
        while not stop.is_set():
            message = pubsub.get_message(timeout=1.0)
            if not message or message.get("type") != "message":
                continue
            raw = message.get("data")
            text = raw.decode("utf-8") if isinstance(raw, bytes) else str(raw or "")
            if text.strip().lower() == "force":
                force_event.set()
    except Exception:
        logger.exception("force listener stopped")
    finally:
        try:
            pubsub.unsubscribe(CMD_CHANNEL)
            pubsub.close()
        except Exception:
            logger.debug("force listener cleanup failed", exc_info=True)


def run_forever() -> None:
    settings = get_settings()
    if not settings.quote_collector_enabled:
        logger.info("QUOTE_COLLECTOR_ENABLED=false，退出")
        return

    interval = _clamp_interval(settings.quote_collect_interval_sec)
    name = (settings.quote_provider or "tickflow").strip().lower()
    if name != "tickflow":
        raise ValueError(f"未知行情 Provider：{settings.quote_provider}")
    provider: QuoteProvider = TickFlowProvider(api_key=settings.tickflow_api_key)

    backoff = interval
    force_event = threading.Event()
    stop = threading.Event()
    client: redis.Redis | None = None

    while not stop.is_set():
        try:
            if client is None:
                client = redis.Redis.from_url(settings.redis_url, decode_responses=True)
                client.ping()
                listen_client = redis.Redis.from_url(settings.redis_url, decode_responses=True)
                threading.Thread(
                    target=_listen_force,
                    args=(listen_client, force_event, stop),
                    name="quote-force",
                    daemon=True,
                ).start()
                backoff = interval

            writer = RedisQuoteWriter(client)
            force = force_event.is_set()
            if force:
                force_event.clear()

            db = SessionLocal()
            try:
                result = collect_once(
                    db=db,
                    writer=writer,
                    provider=provider,
                    client=client,
                    force=force,
                    interval_sec=interval,
                )
                logger.info(
                    "collect: success=%s skipped=%s count=%s msg=%s",
                    result.get("success"),
                    result.get("skipped"),
                    result.get("count"),
                    result.get("message"),
                )
            finally:
                db.close()

            time.sleep(interval)
        except redis.RedisError as exc:
            logger.warning("redis error: %s", exc)
            client = None
            time.sleep(backoff)
            backoff = min(60, backoff * 2)
        except Exception as exc:
            logger.exception("run_forever iteration failed: %s", exc)
            time.sleep(backoff)
            backoff = min(60, max(interval, backoff * 2))

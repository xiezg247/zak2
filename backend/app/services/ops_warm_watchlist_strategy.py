"""自选策略 cache 预热：Redis → PG 桥 + 日 K 双均线启发式。"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.redis_keys import KEY_PREFIX
from app.models.bars import DbBarData
from app.services.ops_bars_fill import list_watchlist_symbols
from app.services.ops_scheduler import save_job_run_meta
from app.services.quotes import get_quote_store
from app.services.strategy_board import DEFAULT_CONFIG_KEY, _parse_payload
from app.services.strategy_signal_ma import compute_ma_signal, parse_config_key
from app.services.symbols import to_vt_symbol

JOB_ID = "warm_watchlist_strategy_cache"
POOL_CAP = 500
_CHINA_TZ = timezone(timedelta(hours=8))


def _redis_client():
    store = get_quote_store()
    if not store.available():
        return None
    return store._client  # noqa: SLF001


def _today() -> str:
    return datetime.now(_CHINA_TZ).date().isoformat()


def _list_config_keys(db: Session) -> list[str]:
    keys = {DEFAULT_CONFIG_KEY}
    rows = db.execute(
        text(
            """
            SELECT value_json FROM auth.user_preferences
            WHERE namespace = 'watchlist' AND key = 'signal_config'
            """
        )
    ).scalars().all()
    for row in rows:
        if not isinstance(row, dict):
            continue
        cls = str(row.get("class_name") or "AshareShortBreakoutStrategy").strip()
        try:
            fast = max(2, min(int(row.get("fast_window") or 5), 60))
            slow = max(fast + 1, min(int(row.get("slow_window") or 10), 120))
        except (TypeError, ValueError):
            continue
        keys.add(f"{cls}:{fast}:{slow}")
    return sorted(keys)


def _upsert_signal(
    db: Session,
    *,
    vt_symbol: str,
    config_key: str,
    bar_as_of: str,
    payload: str,
    updated_at: str,
) -> None:
    db.execute(
        text(
            """
            INSERT INTO cache.watchlist_signal_cache (
                vt_symbol, config_key, bar_as_of, payload, updated_at
            ) VALUES (
                :vt, :ck, :ba, :payload, :ua
            )
            ON CONFLICT (vt_symbol, config_key, bar_as_of) DO UPDATE SET
                payload = EXCLUDED.payload,
                updated_at = EXCLUDED.updated_at
            """
        ),
        {"vt": vt_symbol, "ck": config_key, "ba": bar_as_of, "payload": payload, "ua": updated_at},
    )


def _upsert_position(
    db: Session,
    *,
    vt_symbol: str,
    config_key: str,
    bar_as_of: str,
    position_key: str,
    payload: str,
    updated_at: str,
) -> None:
    db.execute(
        text(
            """
            INSERT INTO cache.watchlist_position_cache (
                vt_symbol, config_key, bar_as_of, position_key, payload, updated_at
            ) VALUES (
                :vt, :ck, :ba, :pk, :payload, :ua
            )
            ON CONFLICT (vt_symbol, config_key, bar_as_of, position_key) DO UPDATE SET
                payload = EXCLUDED.payload,
                updated_at = EXCLUDED.updated_at
            """
        ),
        {
            "vt": vt_symbol,
            "ck": config_key,
            "ba": bar_as_of,
            "pk": position_key,
            "payload": payload,
            "ua": updated_at,
        },
    )


def _bridge_config(db: Session, client: Any, config_key: str) -> tuple[int, int]:
    written_s = 0
    written_p = 0
    today = _today()
    sig_prefix = f"{KEY_PREFIX}:cache:signal:latest:{config_key}:"
    for key in client.scan_iter(match=f"{sig_prefix}*", count=100):
        text_key = key.decode("utf-8") if isinstance(key, bytes) else str(key)
        vt = text_key[len(sig_prefix) :] if text_key.startswith(sig_prefix) else ""
        if not vt:
            continue
        raw = client.get(key)
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8", errors="ignore")
        if not isinstance(raw, str) or not raw.strip():
            continue
        snap = _parse_payload(raw)
        bar_as_of = today
        updated_at = today
        if isinstance(snap, dict):
            bar_as_of = str(snap.get("_bar_as_of") or snap.get("as_of") or today)[:32]
            updated_at = str(snap.get("_updated_at") or today)[:64]
            payload = json.dumps(
                {k: v for k, v in snap.items() if not str(k).startswith("_")},
                ensure_ascii=False,
            )
        else:
            payload = raw
        _upsert_signal(
            db,
            vt_symbol=vt,
            config_key=config_key,
            bar_as_of=bar_as_of or today,
            payload=payload,
            updated_at=updated_at or today,
        )
        written_s += 1

    pos_prefix = f"{KEY_PREFIX}:cache:position:latest:{config_key}:"
    for key in client.scan_iter(match=f"{pos_prefix}*", count=100):
        text_key = key.decode("utf-8") if isinstance(key, bytes) else str(key)
        rest = text_key[len(pos_prefix) :] if text_key.startswith(pos_prefix) else ""
        # rest = "{vt}:{position_key}" — vt 含点号，position_key 为最后一段
        if ":" not in rest:
            continue
        vt, position_key = rest.rsplit(":", 1)
        if not vt or not position_key:
            continue
        raw = client.get(key)
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8", errors="ignore")
        if not isinstance(raw, str) or not raw.strip():
            continue
        snap = _parse_payload(raw)
        bar_as_of = today
        updated_at = today
        if isinstance(snap, dict):
            bar_as_of = str(snap.get("_bar_as_of") or snap.get("as_of") or today)[:32]
            updated_at = str(snap.get("_updated_at") or today)[:64]
            payload = json.dumps(
                {k: v for k, v in snap.items() if not str(k).startswith("_")},
                ensure_ascii=False,
            )
        else:
            payload = raw
        _upsert_position(
            db,
            vt_symbol=vt,
            config_key=config_key,
            bar_as_of=bar_as_of or today,
            position_key=position_key,
            payload=payload,
            updated_at=updated_at or today,
        )
        written_p += 1
    return written_s, written_p


def _load_daily_closes(
    db: Session, *, symbol: str, exchange: str, limit: int
) -> tuple[list[float], list[float], str] | None:
    """返回 (closes, volumes, as_of)；无数据返回 None（不抛）。"""
    from app.services.symbols import normalize_exchange

    exch = normalize_exchange(exchange)
    rows = list(
        db.scalars(
            select(DbBarData)
            .where(
                DbBarData.symbol == symbol,
                DbBarData.exchange == exch,
                DbBarData.interval == "d",
            )
            .order_by(DbBarData.datetime.desc())
            .limit(limit)
        )
    )
    if not rows:
        return None
    rows.reverse()
    closes = [float(r.close_price or 0) for r in rows]
    volumes = [float(r.volume or 0) for r in rows]
    as_of = rows[-1].datetime.date().isoformat()
    return closes, volumes, as_of


def _compute_pool(db: Session, config_keys: list[str]) -> tuple[int, int]:
    pool = list_watchlist_symbols(db)[:POOL_CAP]
    computed = 0
    skipped_bars = 0
    today = _today()
    for ck in config_keys:
        parsed = parse_config_key(ck)
        if not parsed:
            continue
        fast, slow = parsed
        limit = min(200, max(slow * 3, 60))
        for symbol, exchange in pool:
            loaded = _load_daily_closes(db, symbol=symbol, exchange=exchange, limit=limit)
            if not loaded:
                skipped_bars += 1
                continue
            closes, volumes, as_of = loaded
            vt = to_vt_symbol(symbol, exchange)
            snap = compute_ma_signal(
                closes,
                volumes=volumes,
                fast=fast,
                slow=slow,
                vt_symbol=vt,
                as_of=as_of,
            )
            if not snap:
                skipped_bars += 1
                continue
            _upsert_signal(
                db,
                vt_symbol=vt,
                config_key=ck,
                bar_as_of=as_of,
                payload=json.dumps(snap, ensure_ascii=False),
                updated_at=today,
            )
            computed += 1
    return computed, skipped_bars


def warm_watchlist_strategy_cache(db: Session) -> dict[str, Any]:
    config_keys = _list_config_keys(db)
    client = _redis_client()
    written_s = 0
    written_p = 0
    if client is not None:
        for ck in config_keys:
            s, p = _bridge_config(db, client, ck)
            written_s += s
            written_p += p
        db.commit()
    computed, skipped_bars = _compute_pool(db, config_keys)
    db.commit()
    msg = (
        f"策略 cache：桥接 signals={written_s} positions={written_p}；"
        f"双均线启发式 v2（确认 N=2） computed={computed} skipped_bars={skipped_bars}"
    )
    save_job_run_meta(db, JOB_ID, last_message=msg, last_success=True)
    return {
        "success": True,
        "skipped": False,
        "message": msg,
        "written_signals": written_s,
        "written_positions": written_p,
        "computed": computed,
        "skipped_bars": skipped_bars,
    }

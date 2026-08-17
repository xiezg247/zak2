"""自选策略 cache 预热：Redis → PG 桥 + 日 K 双均线启发式。"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.redis_keys import KEY_PREFIX
from app.models.bars import DbBarData
from app.services.ops.bars_fill import list_watchlist_symbols
from app.services.ops.scheduler import save_job_run_meta
from app.services.quotes import get_quote_store
from app.services.strategy_board import DEFAULT_CONFIG_KEY, _parse_payload
from app.services.strategy_signal_ma import (
    TREND_ADX_PERIOD,
    TREND_ADX_THRESHOLD,
    TREND_MA_FAST,
    TREND_MA_SLOW,
    compute_double_ma_signal,
    compute_ma_signal,
    compute_trend_ma_signal,
    parse_config_key,
)
from app.services.symbols import to_vt_symbol

JOB_ID = "warm_watchlist_strategy_cache"
POOL_CAP = 500
_CHINA_TZ = timezone(timedelta(hours=8))


def _redis_client():
    store = get_quote_store()
    if not store.available():
        return None
    return store._client


def _today() -> str:
    return datetime.now(_CHINA_TZ).date().isoformat()


def _list_config_keys(db: Session) -> list[str]:
    keys = {DEFAULT_CONFIG_KEY}
    rows = (
        db.execute(
            text(
                """
            SELECT value_json FROM auth.user_preferences
            WHERE namespace = 'watchlist' AND key = 'signal_config'
            """
            )
        )
        .scalars()
        .all()
    )
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


def _load_daily_bars(
    db: Session, *, symbol: str, exchange: str, limit: int
) -> tuple[list[float], list[float], list[float], list[float], str] | None:
    """返回 (highs, lows, closes, volumes, as_of)；无数据返回 None（不抛）。"""
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
    highs = [float(r.high_price or 0) for r in rows]
    lows = [float(r.low_price or 0) for r in rows]
    closes = [float(r.close_price or 0) for r in rows]
    volumes = [float(r.volume or 0) for r in rows]
    as_of = rows[-1].datetime.date().isoformat()
    return highs, lows, closes, volumes, as_of


def _compute_pool(db: Session, config_keys: list[str]) -> tuple[int, int]:
    pool = list_watchlist_symbols(db)[:POOL_CAP]
    computed = 0
    skipped_bars = 0
    today = _today()
    seen_dm: set[tuple[int, int]] = set()

    def _upsert_one(
        *,
        vt: str,
        config_key: str,
        as_of: str,
        snap: dict[str, Any],
    ) -> None:
        nonlocal computed
        _upsert_signal(
            db,
            vt_symbol=vt,
            config_key=config_key,
            bar_as_of=as_of,
            payload=json.dumps(snap, ensure_ascii=False),
            updated_at=today,
        )
        computed += 1

    for ck in config_keys:
        parsed = parse_config_key(ck)
        if not parsed:
            continue
        fast, slow = parsed
        limit = min(200, max(slow * 3, 60))
        for symbol, exchange in pool:
            loaded = _load_daily_bars(db, symbol=symbol, exchange=exchange, limit=limit)
            if not loaded:
                skipped_bars += 1
                continue
            highs, lows, closes, volumes, as_of = loaded
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
            _upsert_one(vt=vt, config_key=ck, as_of=as_of, snap=snap)

            dm_key = f"double_ma:{fast}:{slow}"
            dm = compute_double_ma_signal(
                closes,
                volumes=volumes,
                fast=fast,
                slow=slow,
                vt_symbol=vt,
                as_of=as_of,
            )
            if dm:
                _upsert_one(vt=vt, config_key=dm_key, as_of=as_of, snap=dm)
                seen_dm.add((fast, slow))

    # 保证至少有默认回测窗口 5:20
    if (5, 20) not in seen_dm and pool:
        limit = min(200, max(20 * 3, 60))
        for symbol, exchange in pool:
            loaded = _load_daily_bars(db, symbol=symbol, exchange=exchange, limit=limit)
            if not loaded:
                continue
            _highs, _lows, closes, volumes, as_of = loaded
            vt = to_vt_symbol(symbol, exchange)
            dm = compute_double_ma_signal(
                closes,
                volumes=volumes,
                fast=5,
                slow=20,
                vt_symbol=vt,
                as_of=as_of,
            )
            if not dm:
                continue
            _upsert_one(vt=vt, config_key="double_ma:5:20", as_of=as_of, snap=dm)
        seen_dm.add((5, 20))

    # 第三轨 trend_ma:20:60
    if pool:
        tm_key = f"trend_ma:{TREND_MA_FAST}:{TREND_MA_SLOW}"
        limit_tm = min(200, max(TREND_MA_SLOW * 3, TREND_ADX_PERIOD * 4, 80))
        for symbol, exchange in pool:
            loaded = _load_daily_bars(db, symbol=symbol, exchange=exchange, limit=limit_tm)
            if not loaded:
                continue
            highs, lows, closes, volumes, as_of = loaded
            vt = to_vt_symbol(symbol, exchange)
            tm = compute_trend_ma_signal(
                highs,
                lows,
                closes,
                volumes=volumes,
                fast=TREND_MA_FAST,
                slow=TREND_MA_SLOW,
                adx_period=TREND_ADX_PERIOD,
                adx_threshold=TREND_ADX_THRESHOLD,
                vt_symbol=vt,
                as_of=as_of,
            )
            if not tm:
                continue
            _upsert_one(vt=vt, config_key=tm_key, as_of=as_of, snap=tm)

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
        f"启发式 v2 + double_ma + trend_ma 三轨 computed={computed} skipped_bars={skipped_bars}"
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

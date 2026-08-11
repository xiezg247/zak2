"""自选策略看盘：只读信号 / 持仓（复用桌面 Redis/PG cache，不跑策略）。"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services import watchlist_repo as repo
from app.services import signal_panel_repo
from app.services.off_plan import (
    build_plan_symbol_statuses,
    list_off_plan_vt_symbols,
    load_active_plan_snapshot,
)
from app.services.position_risk_tags import compute_position_risk_tags, primary_risk_tag
from app.services.quotes import get_quote_store
from app.services.symbols import to_tf_symbol, to_vt_symbol
from app.services.trading_risk import (
    compute_actual_position_pct,
    load_trading_risk_prefs,
    normalize_plan_max_pct,
)
from app.core.redis_keys import KEY_PREFIX
from app.services.tushare_screener import latest_open_yyyymmdd

DEFAULT_CONFIG_KEY = "AshareShortBreakoutStrategy:5:10"
_CHINA_TZ = timezone(timedelta(hours=8))


def _safe_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_payload(raw: str | None) -> dict[str, Any] | None:
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(data, dict):
        return None
    # Redis envelope
    inner = data.get("payload")
    if isinstance(inner, str) and inner.strip().startswith("{"):
        try:
            snap = json.loads(inner)
            if isinstance(snap, dict):
                snap["_bar_as_of"] = str(data.get("bar_as_of") or snap.get("as_of") or "")
                snap["_updated_at"] = str(data.get("updated_at") or "")
                return snap
        except (json.JSONDecodeError, TypeError):
            return None
    if "signal" in data or "vt_symbol" in data:
        return data
    return None


def resolve_config_key(db: Session, user_id: str, override: str | None = None) -> str:
    if override and override.strip():
        return override.strip()
    row = db.execute(
        text(
            """
            SELECT value_json FROM auth.user_preferences
            WHERE user_id = CAST(:uid AS uuid)
              AND namespace = 'watchlist' AND key = 'signal_config'
            LIMIT 1
            """
        ),
        {"uid": user_id},
    ).scalar()
    if isinstance(row, dict):
        cls = str(row.get("class_name") or "AshareShortBreakoutStrategy").strip()
        try:
            fast = max(2, min(int(row.get("fast_window") or 5), 60))
            slow = max(fast + 1, min(int(row.get("slow_window") or 10), 120))
        except (TypeError, ValueError):
            return DEFAULT_CONFIG_KEY
        return f"{cls}:{fast}:{slow}"
    return DEFAULT_CONFIG_KEY


def _redis_client():
    store = get_quote_store()
    if not store.available():
        return None
    return store._client  # noqa: SLF001 — 与 QuoteStore 共用连接


def _load_signal_redis(config_key: str, vt_symbol: str) -> dict[str, Any] | None:
    client = _redis_client()
    if client is None:
        return None
    key = f"{KEY_PREFIX}:cache:signal:latest:{config_key}:{vt_symbol}"
    try:
        raw = client.get(key)
    except Exception:  # noqa: BLE001
        return None
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8", errors="ignore")
    return _parse_payload(raw if isinstance(raw, str) else None)


def _scan_signal_redis(config_key: str, *, limit: int = 30) -> list[tuple[str, dict[str, Any]]]:
    client = _redis_client()
    if client is None:
        return []
    pattern = f"{KEY_PREFIX}:cache:signal:latest:{config_key}:*"
    prefix = f"{KEY_PREFIX}:cache:signal:latest:{config_key}:"
    out: list[tuple[str, dict[str, Any]]] = []
    try:
        for key in client.scan_iter(match=pattern, count=100):
            text_key = key.decode("utf-8") if isinstance(key, bytes) else str(key)
            vt = text_key[len(prefix) :] if text_key.startswith(prefix) else ""
            if not vt:
                continue
            raw = client.get(key)
            if isinstance(raw, bytes):
                raw = raw.decode("utf-8", errors="ignore")
            snap = _parse_payload(raw if isinstance(raw, str) else None)
            if snap:
                out.append((vt, snap))
            if len(out) >= limit:
                break
    except Exception:  # noqa: BLE001
        return out
    return out


def _load_signals_pg(db: Session, config_key: str, vt_symbols: list[str]) -> dict[str, dict[str, Any]]:
    if not vt_symbols:
        return {}
    rows = db.execute(
        text(
            """
            SELECT DISTINCT ON (vt_symbol)
              vt_symbol, bar_as_of, payload, updated_at
            FROM cache.watchlist_signal_cache
            WHERE config_key = :ck AND vt_symbol = ANY(:vts)
            ORDER BY vt_symbol, updated_at DESC
            """
        ),
        {"ck": config_key, "vts": vt_symbols},
    ).mappings().all()
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        snap = _parse_payload(row["payload"])
        if not snap:
            continue
        snap["_bar_as_of"] = str(row["bar_as_of"] or "")
        snap["_updated_at"] = str(row["updated_at"] or "")
        out[str(row["vt_symbol"])] = snap
    return out


def _load_position_signal_redis(config_key: str, vt_symbol: str, position_key: str) -> dict[str, Any] | None:
    client = _redis_client()
    if client is None:
        return None
    key = f"{KEY_PREFIX}:cache:position:latest:{config_key}:{vt_symbol}:{position_key}"
    try:
        raw = client.get(key)
    except Exception:  # noqa: BLE001
        return None
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8", errors="ignore")
    return _parse_payload(raw if isinstance(raw, str) else None)


def _load_position_signal_pg(
    db: Session, config_key: str, vt_symbol: str, position_key: str
) -> dict[str, Any] | None:
    row = db.execute(
        text(
            """
            SELECT payload, bar_as_of, updated_at
            FROM cache.watchlist_position_cache
            WHERE config_key = :ck AND vt_symbol = :vt AND position_key = :pk
            ORDER BY updated_at DESC
            LIMIT 1
            """
        ),
        {"ck": config_key, "vt": vt_symbol, "pk": position_key},
    ).mappings().first()
    if not row:
        return None
    snap = _parse_payload(row["payload"])
    if snap:
        snap["_bar_as_of"] = str(row["bar_as_of"] or "")
        snap["_updated_at"] = str(row["updated_at"] or "")
    return snap


def _china_today() -> date:
    return datetime.now(_CHINA_TZ).date()


def _t1_locked(buy_date: str) -> bool:
    text_v = (buy_date or "").strip()[:10]
    if not text_v:
        return False
    try:
        parsed = datetime.strptime(text_v, "%Y-%m-%d").date()
    except ValueError:
        return False
    return parsed >= _china_today()


def _signal_label(kind: str) -> str:
    return {"buy": "买入", "sell": "卖出", "hold": "观望", "na": "—"}.get(kind, kind or "—")


def enrich_position_risk(
    row: dict[str, Any],
    *,
    change_pct: float | None,
    volume_ratio: float | None,
    off_plan: bool = False,
) -> dict[str, Any]:
    row["off_plan"] = bool(off_plan)
    tags = compute_position_risk_tags(
        exit_signal=str(row.get("exit_signal") or ""),
        unrealized_pnl_pct=row.get("unrealized_pnl_pct"),
        change_pct=change_pct,
        volume_ratio=volume_ratio,
        off_plan=off_plan,
    )
    row["risk_tags"] = tags
    row["risk_primary"] = primary_risk_tag(tags)
    return row


def _resolve_plan_trade_date(db: Session, as_of: str | None) -> str:
    text_v = (as_of or "").strip()[:10]
    if len(text_v) == 10 and text_v[4] == "-" and text_v[7] == "-":
        return text_v
    ymd = latest_open_yyyymmdd(db)
    ymd = str(ymd).replace("-", "")[:8]
    if len(ymd) == 8 and ymd.isdigit():
        return f"{ymd[:4]}-{ymd[4:6]}-{ymd[6:8]}"
    return text_v


def _pack_signal_row(
    vt_symbol: str,
    snap: dict[str, Any],
    *,
    name: str = "",
    last_price: float | None = None,
    change_pct: float | None = None,
) -> dict[str, Any]:
    kind = str(snap.get("signal") or "na")
    price = last_price if last_price is not None else _safe_float(snap.get("last_close"))
    return {
        "vt_symbol": vt_symbol,
        "name": name or str(snap.get("name") or ""),
        "last_price": price,
        "change_pct": change_pct,
        "signal": kind,
        "signal_label": str(snap.get("signal_label") or _signal_label(kind)),
        "signal_date": str(snap.get("signal_date") or "")[:10] or None,
        "strength": _safe_float(snap.get("strength")),
        "reason_summary": str(snap.get("reason_summary") or ""),
        "ref_buy_price": _safe_float(snap.get("ref_buy_price")),
        "ref_sell_price": _safe_float(snap.get("ref_sell_price")),
        "ma_gap_pct": _safe_float(snap.get("ma_gap_pct")),
        "volume_ratio_5d": _safe_float(snap.get("volume_ratio_5d")),
        "bar_as_of": str(snap.get("_bar_as_of") or snap.get("as_of") or "")[:10] or None,
        "updated_at": str(snap.get("_updated_at") or "") or None,
    }


def load_strategy_board(
    db: Session,
    user_id: str,
    *,
    config_key: str | None = None,
) -> dict[str, Any]:
    ck = resolve_config_key(db, user_id, config_key)
    items = repo.list_items(db, user_id)
    name_by_vt = {
        to_vt_symbol(i.symbol, i.exchange): (i.name or "") for i in items
    }
    watchlist_vts = list(name_by_vt.keys())
    panel_symbols = signal_panel_repo.load_symbols(db, user_id)
    # 名单优先；空则回退自选
    universe = panel_symbols if panel_symbols else watchlist_vts

    # 行情（自选 + 名单并集）
    quote_vts = list(dict.fromkeys([*watchlist_vts, *panel_symbols]))
    quote_by_vt: dict[str, Any] = {}
    store = get_quote_store()
    if store.available() and quote_vts:
        tfs = []
        tf_to_vt: dict[str, str] = {}
        for vt in quote_vts:
            if "." not in vt:
                continue
            code, exch = vt.rsplit(".", 1)
            tf = to_tf_symbol(code, exch)
            tfs.append(tf)
            tf_to_vt[tf] = vt
        for q in store.get_quotes(tfs):
            vt = tf_to_vt.get(q.symbol)
            if vt:
                quote_by_vt[vt] = q
                if not name_by_vt.get(vt) and q.name:
                    name_by_vt[vt] = q.name

    source = "none"
    signals: list[dict[str, Any]] = []
    seen: set[str] = set()

    # 1) 宇宙 ∩ Redis（保持 universe 顺序）
    for vt in universe:
        snap = _load_signal_redis(ck, vt)
        if snap:
            source = "redis"
            q = quote_by_vt.get(vt)
            signals.append(
                _pack_signal_row(
                    vt,
                    snap,
                    name=name_by_vt.get(vt, ""),
                    last_price=getattr(q, "last_price", None) if q else None,
                    change_pct=getattr(q, "change_pct", None) if q else None,
                )
            )
            seen.add(vt)

    # 2) 宇宙 ∩ PG 补缺
    missing = [vt for vt in universe if vt not in seen]
    if missing:
        pg_hits = _load_signals_pg(db, ck, missing)
        if pg_hits and source == "none":
            source = "pg"
        elif pg_hits and source == "redis":
            source = "redis+pg"
        for vt in missing:
            snap = pg_hits.get(vt)
            if not snap:
                continue
            q = quote_by_vt.get(vt)
            signals.append(
                _pack_signal_row(
                    vt,
                    snap,
                    name=name_by_vt.get(vt, ""),
                    last_price=getattr(q, "last_price", None) if q else None,
                    change_pct=getattr(q, "change_pct", None) if q else None,
                )
            )
            seen.add(vt)

    # 3) 无名单且仍空：扫 Redis 该 config 的 latest（桌面本地名单不在 PG）
    if not signals and not panel_symbols:
        scanned = _scan_signal_redis(ck, limit=30)
        if scanned:
            source = "redis"
            for vt, snap in scanned:
                signals.append(_pack_signal_row(vt, snap, name=name_by_vt.get(vt, "")))

    # 有名单时：按名单顺序；否则按强度
    if panel_symbols:
        order = {vt: i for i, vt in enumerate(panel_symbols)}
        signals.sort(key=lambda r: order.get(str(r.get("vt_symbol")), 999))
    else:
        signals.sort(key=lambda r: float(r.get("strength") or -1), reverse=True)

    as_of = ""
    for s in signals:
        if s.get("bar_as_of"):
            as_of = str(s["bar_as_of"])
            break

    trade_date = _resolve_plan_trade_date(db, as_of or None)
    prefs = load_trading_risk_prefs(db, user_id)
    plan_snap = load_active_plan_snapshot(db, user_id, trade_date)
    plan_vts: set[str] | None = plan_snap["vt_symbols"] if plan_snap else None

    # 持仓记账
    pos_rows = db.execute(
        text(
            """
            SELECT symbol, exchange, cost_price, volume, buy_date, notes, source, plan_pct, sort_order
            FROM app.watchlist_positions
            WHERE user_id = CAST(:uid AS uuid)
            ORDER BY sort_order, buy_date DESC
            """
        ),
        {"uid": user_id},
    ).mappings().all()

    position_vts = [to_vt_symbol(str(r["symbol"]), str(r["exchange"])) for r in pos_rows]
    off_set = set(list_off_plan_vt_symbols(position_vts, plan_vts))

    positions: list[dict[str, Any]] = []
    for row in pos_rows:
        symbol = str(row["symbol"])
        exchange = str(row["exchange"])
        vt = to_vt_symbol(symbol, exchange)
        cost = float(row["cost_price"] or 0)
        volume = int(row["volume"] or 0)
        buy_date = str(row["buy_date"] or "")[:10]
        position_key = f"{cost}:{volume}:{buy_date}"
        q = quote_by_vt.get(vt)
        last = getattr(q, "last_price", None) if q else None
        if last is None or last <= 0:
            last = None
        market_value = pnl = pnl_pct = None
        if last is not None and last > 0 and cost > 0 and volume > 0:
            market_value = round(last * volume, 2)
            pnl = round(market_value - cost * volume, 2)
            pnl_pct = round((last - cost) / cost * 100, 2)

        exit_snap = _load_position_signal_redis(ck, vt, position_key) or _load_position_signal_pg(
            db, ck, vt, position_key
        )
        if exit_snap is None:
            exit_snap = _load_signal_redis(ck, vt)
        exit_kind = str((exit_snap or {}).get("signal") or "na")
        pos_change_pct: float | None = None
        pos_volume_ratio: float | None = None
        if q is not None:
            pos_change_pct = float(getattr(q, "change_pct", 0) or 0)
            pos_volume_ratio = float(getattr(q, "volume_ratio", 0) or 0)
        op = vt in off_set
        positions.append(
            enrich_position_risk(
                {
                    "vt_symbol": vt,
                    "name": name_by_vt.get(vt) or (getattr(q, "name", "") if q else ""),
                    "cost_price": cost,
                    "volume": volume,
                    "buy_date": buy_date,
                    "notes": str(row["notes"] or ""),
                    "source": str(row["source"] or "manual"),
                    "plan_pct": _safe_float(row["plan_pct"]),
                    "last_price": last,
                    "market_value": market_value,
                    "unrealized_pnl": pnl,
                    "unrealized_pnl_pct": pnl_pct,
                    "t1_locked": _t1_locked(buy_date),
                    "exit_signal": exit_kind,
                    "exit_signal_label": _signal_label(exit_kind),
                    "ref_sell_price": _safe_float((exit_snap or {}).get("ref_sell_price")),
                    "reason_summary": str((exit_snap or {}).get("reason_summary") or ""),
                },
                change_pct=pos_change_pct,
                volume_ratio=pos_volume_ratio,
                off_plan=op,
            )
        )

    total_mv = sum(float(p["market_value"] or 0) for p in positions)
    if plan_snap is None:
        ordered_plan = []
    else:
        ordered_plan = list(plan_snap.get("ordered_vt_symbols") or [])
        if not ordered_plan:
            ordered_plan = sorted(plan_snap.get("vt_symbols") or [])

    plan_symbols = build_plan_symbol_statuses(
        ordered_vt_symbols=ordered_plan,
        watchlist_vts=set(watchlist_vts),
        position_vts=set(position_vts),
        name_by_vt={k: (v or "") for k, v in name_by_vt.items()},
    )
    risk_summary = {
        "total_capital": prefs.get("total_capital"),
        "actual_position_pct": compute_actual_position_pct(total_mv, prefs.get("total_capital")),
        "plan_max_pct": (
            normalize_plan_max_pct(float(plan_snap["max_position_pct"]))
            if plan_snap is not None
            else None
        ),
        "off_plan_count": len(off_set),
        "off_plan_symbols": sorted(off_set),
        "active_plan_date": str(plan_snap["trade_date"]) if plan_snap else "",
        "plan_symbols": plan_symbols,
    }

    note = ""
    if panel_symbols and not signals:
        note = f"信号名单 {len(panel_symbols)} 只，暂无策略 cache（可于桌面刷新信号）。"
    elif not signals and not positions:
        note = "暂无策略缓存。请在 zak 桌面刷新信号/持仓，或确认 Redis/PG cache 已写入。"
    elif not signals:
        note = "持仓来自记账表；信号 cache 为空（可于桌面点刷新信号）。"

    return {
        "config_key": ck,
        "as_of": as_of or None,
        "source": source,
        "note": note,
        "panel_symbols": panel_symbols,
        "signals": signals,
        "positions": positions,
        "risk_summary": risk_summary,
    }

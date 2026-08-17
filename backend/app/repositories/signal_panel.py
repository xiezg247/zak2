"""自选信号名单（PG user_preferences，Web 侧；与桌面本地 UI 暂不同步）。"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.repositories import watchlist as wl_repo
from app.services.symbols import to_vt_symbol

NAMESPACE = "watchlist"
PREF_KEY = "signal_panel_symbols"
SIGNAL_PANEL_MAX_SYMBOLS = 10


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def normalize_symbols(symbols: list[str], *, max_count: int = SIGNAL_PANEL_MAX_SYMBOLS) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    limit = max(1, int(max_count))
    for raw in symbols:
        text_sym = str(raw or "").strip()
        if not text_sym:
            continue
        try:
            symbol, exchange = wl_repo.resolve_symbol_pair(text_sym)
            vt = to_vt_symbol(symbol, exchange)
        except Exception:  # noqa: BLE001
            continue
        if vt not in seen:
            seen.add(vt)
            cleaned.append(vt)
            if len(cleaned) >= limit:
                break
    return cleaned


def load_symbols(db: Session, user_id: str) -> list[str]:
    row = db.execute(
        text(
            """
            SELECT value_json FROM auth.user_preferences
            WHERE user_id = CAST(:uid AS uuid)
              AND namespace = :ns AND key = :key
            LIMIT 1
            """
        ),
        {"uid": user_id, "ns": NAMESPACE, "key": PREF_KEY},
    ).scalar()
    if not isinstance(row, dict):
        return []
    raw = row.get("symbols")
    if isinstance(raw, str):
        parts = [p.strip() for p in raw.split(",") if p.strip()]
        return normalize_symbols(parts)
    if isinstance(raw, list):
        return normalize_symbols([str(x) for x in raw])
    return []


def save_symbols(db: Session, user_id: str, symbols: list[str]) -> list[str]:
    cleaned = normalize_symbols(symbols)
    payload: dict[str, Any] = {"symbols": cleaned}
    db.execute(
        text(
            """
            INSERT INTO auth.user_preferences (user_id, namespace, key, value_json, updated_at)
            VALUES (CAST(:uid AS uuid), :ns, :key, CAST(:val AS jsonb), CAST(:now AS timestamptz))
            ON CONFLICT (user_id, namespace, key)
            DO UPDATE SET value_json = EXCLUDED.value_json, updated_at = EXCLUDED.updated_at
            """
        ),
        {
            "uid": user_id,
            "ns": NAMESPACE,
            "key": PREF_KEY,
            "val": json.dumps(payload, ensure_ascii=False),
            "now": _now_iso(),
        },
    )
    db.commit()
    return cleaned


def add_symbol(db: Session, user_id: str, raw: str) -> list[str]:
    current = load_symbols(db, user_id)
    try:
        symbol, exchange = wl_repo.resolve_symbol_pair(raw)
        vt = to_vt_symbol(symbol, exchange)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"标的无效：{exc}") from exc
    if vt in current:
        return current
    if len(current) >= SIGNAL_PANEL_MAX_SYMBOLS:
        raise HTTPException(status_code=400, detail=f"信号名单已满（上限 {SIGNAL_PANEL_MAX_SYMBOLS}）")
    return save_symbols(db, user_id, [*current, vt])


def remove_symbol(db: Session, user_id: str, raw: str) -> list[str]:
    try:
        symbol, exchange = wl_repo.resolve_symbol_pair(raw)
        vt = to_vt_symbol(symbol, exchange)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"标的无效：{exc}") from exc
    current = load_symbols(db, user_id)
    if vt not in current:
        raise HTTPException(status_code=404, detail="不在信号名单中")
    return save_symbols(db, user_id, [s for s in current if s != vt])


def panel_payload(db: Session, user_id: str) -> dict[str, Any]:
    symbols = load_symbols(db, user_id)
    return {
        "symbols": symbols,
        "max_symbols": SIGNAL_PANEL_MAX_SYMBOLS,
        "count": len(symbols),
    }

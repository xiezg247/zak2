"""自选信号名单（PG user_preferences，Web 侧；与桌面本地 UI 暂不同步）。

非 ORM 仓库，不继承 BaseRepository，保持 ``SignalPanelRepository(db, user_id)``。
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.repositories.watchlist import resolve_symbol_pair
from app.schemas.watchlist import SignalPanelOut
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
            symbol, exchange = resolve_symbol_pair(text_sym)
            vt = to_vt_symbol(symbol, exchange)
        except Exception:
            continue
        if vt not in seen:
            seen.add(vt)
            cleaned.append(vt)
            if len(cleaned) >= limit:
                break
    return cleaned


class SignalPanelRepository:
    """信号名单仓库（原生 SQL 操作 auth.user_preferences）。"""

    def __init__(self, db: Session, user_id: str) -> None:
        self.db = db
        self.user_id = user_id

    def load_symbols(self) -> list[str]:
        row = self.db.execute(
            text(
                """
                SELECT value_json FROM auth.user_preferences
                WHERE user_id = CAST(:uid AS uuid)
                  AND namespace = :ns AND key = :key
                LIMIT 1
                """
            ),
            {"uid": self.user_id, "ns": NAMESPACE, "key": PREF_KEY},
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

    def save_symbols(self, symbols: list[str]) -> list[str]:
        cleaned = normalize_symbols(symbols)
        payload: dict[str, Any] = {"symbols": cleaned}
        self.db.execute(
            text(
                """
                INSERT INTO auth.user_preferences (user_id, namespace, key, value_json, updated_at)
                VALUES (CAST(:uid AS uuid), :ns, :key, CAST(:val AS jsonb), CAST(:now AS timestamptz))
                ON CONFLICT (user_id, namespace, key)
                DO UPDATE SET value_json = EXCLUDED.value_json, updated_at = EXCLUDED.updated_at
                """
            ),
            {
                "uid": self.user_id,
                "ns": NAMESPACE,
                "key": PREF_KEY,
                "val": json.dumps(payload, ensure_ascii=False),
                "now": _now_iso(),
            },
        )
        self.db.commit()
        return cleaned

    def add_symbol(self, raw: str) -> list[str]:
        current = self.load_symbols()
        try:
            symbol, exchange = resolve_symbol_pair(raw)
            vt = to_vt_symbol(symbol, exchange)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"标的无效：{exc}") from exc
        if vt in current:
            return current
        if len(current) >= SIGNAL_PANEL_MAX_SYMBOLS:
            raise HTTPException(status_code=400, detail=f"信号名单已满（上限 {SIGNAL_PANEL_MAX_SYMBOLS}）")
        return self.save_symbols([*current, vt])

    def remove_symbol(self, raw: str) -> list[str]:
        try:
            symbol, exchange = resolve_symbol_pair(raw)
            vt = to_vt_symbol(symbol, exchange)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"标的无效：{exc}") from exc
        current = self.load_symbols()
        if vt not in current:
            raise HTTPException(status_code=404, detail="不在信号名单中")
        return self.save_symbols([s for s in current if s != vt])

    def panel_payload(self) -> SignalPanelOut:
        symbols = self.load_symbols()
        return SignalPanelOut(
            symbols=symbols,
            max_symbols=SIGNAL_PANEL_MAX_SYMBOLS,
            count=len(symbols),
        )

"""只读投研工具实现，供 ai_tools 与 skill.py 共用。"""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.domains.content import notes
from app.domains.market import overview as market
from app.domains.market.quotes import get_quote_store
from app.domains.radar import cards as radar
from app.domains.screener import repository as screener_repo
from app.domains.watchlist import positions_repo, signal_panel_repo, trading_risk
from app.domains.watchlist import repository as watchlist_repo
from app.services.strategy import strategy_board
from app.services.symbols import to_vt_symbol


def get_watchlist(db: Session, user_id: str, args: dict[str, Any]) -> Any:
    limit = max(1, min(int(args.get("limit") or 30), 50))
    with_quotes = bool(args.get("with_quotes", True))
    items = watchlist_repo.WatchlistItemRepository(db, user_id).list_items()[:limit]
    rows: list[dict[str, Any]] = []
    for item in items:
        row = {
            "symbol": item.symbol,
            "exchange": item.exchange,
            "vt_symbol": to_vt_symbol(item.symbol, item.exchange),
            "name": item.name or "",
        }
        rows.append(row)
    if with_quotes and rows:
        store = get_quote_store()
        try:
            from app.services.symbols import to_tf_symbol

            tf_map = {to_tf_symbol(r["symbol"], r["exchange"]): r for r in rows}
            quotes = store.get_quotes(list(tf_map.keys()))
            for q in quotes:
                target = tf_map.get(q.symbol)
                if target:
                    target["last_price"] = q.last_price
                    target["change_pct"] = q.change_pct
                    target["name"] = target["name"] or q.name
        except Exception:
            pass
    return {"count": len(rows), "items": rows}


def get_market_emotion(db: Session, user_id: str, args: dict[str, Any]) -> Any:
    _ = user_id, args
    emotion = market.load_emotion(db)
    overview = market.market_overview(db)
    return {
        "emotion": emotion.model_dump() if isinstance(emotion, BaseModel) else emotion,
        "overview": overview.model_dump() if isinstance(overview, BaseModel) else overview,
    }


def get_recent_screening(db: Session, user_id: str, args: dict[str, Any]) -> Any:
    limit = max(1, min(int(args.get("limit") or 1), 5))
    top_n = max(1, min(int(args.get("top_n") or 20), 50))
    runs = screener_repo.ScreenerRunRepository(db, user_id).list_runs(limit=limit)
    out: list[dict[str, Any]] = []
    for run in runs:
        symbols: list[Any] = []
        try:
            result = json.loads(run.result_json or "{}")
            if isinstance(result, list):
                symbols = result[:top_n]
            elif isinstance(result, dict):
                symbols = list(result.get("rows") or result.get("items") or [])[:top_n]
            else:
                symbols = []
        except json.JSONDecodeError:
            symbols = []
        out.append(
            {
                "id": run.id,
                "condition": run.condition,
                "source": run.source,
                "row_count": run.row_count,
                "total_scanned": run.total_scanned,
                "created_at": run.created_at,
                "top_rows": symbols,
            }
        )
    return {"runs": out}


def get_radar_snapshot(db: Session, user_id: str, args: dict[str, Any]) -> Any:
    _ = user_id
    card_id = str(args.get("card_id") or "").strip()
    max_rows = max(1, min(int(args.get("max_rows") or 15), 30))
    if card_id:
        card = radar.get_radar_card(db, card_id)
        cards = [card] if card else []
    else:
        cards = radar.list_radar_cards(db)
    payload = []
    for c in cards:
        data = c.model_dump() if hasattr(c, "model_dump") else dict(c)
        rows = list(data.get("rows") or [])[:max_rows]
        data["rows"] = rows
        payload.append(data)
    return {"cards": payload}


def list_note_symbols(db: Session, user_id: str, args: dict[str, Any]) -> Any:
    limit = max(1, min(int(args.get("limit") or 30), 50))
    rows = notes.list_note_symbols(db, user_id)[:limit]
    symbols = [r.model_dump() if hasattr(r, "model_dump") else dict(r) for r in rows]
    return {"count": len(symbols), "symbols": symbols}


def get_stock_notes(db: Session, user_id: str, args: dict[str, Any]) -> Any:
    raw = str(args.get("vt_symbol") or args.get("symbol") or "").strip()
    if not raw:
        return {"error": "需要 vt_symbol 或 symbol，例如 600519.SSE"}
    entry_limit = max(1, min(int(args.get("entry_limit") or 20), 50))
    memo = notes.get_memo(db, user_id, raw)
    entries = notes.list_entries(db, user_id, raw, limit=entry_limit)
    memo_d = memo.model_dump() if hasattr(memo, "model_dump") else dict(memo)
    entry_ds = [e.model_dump() if hasattr(e, "model_dump") else dict(e) for e in entries]
    return {"memo": memo_d, "entries": entry_ds, "entry_count": len(entry_ds)}


def get_positions(db: Session, user_id: str, args: dict[str, Any]) -> Any:
    limit = max(1, min(int(args.get("limit") or 20), 20))
    with_quotes = bool(args.get("with_quotes", True))
    items = [
        r.model_dump() if isinstance(r, BaseModel) else r
        for r in positions_repo.PositionRepository(db, user_id).list_positions()[:limit]
    ]
    if with_quotes and items:
        try:
            from app.services.symbols import to_tf_symbol

            store = get_quote_store()
            tf_map = {to_tf_symbol(r["symbol"], r["exchange"]): r for r in items}
            quotes = store.get_quotes(list(tf_map.keys()))
            for q in quotes:
                target = tf_map.get(q.symbol)
                if target is None:
                    continue
                target["last_price"] = q.last_price
                target["change_pct"] = q.change_pct
                if getattr(q, "name", None):
                    target["name"] = q.name
        except Exception:
            pass
    return {"count": len(items), "items": items}


def get_signal_panel(db: Session, user_id: str, args: dict[str, Any]) -> Any:
    _ = args
    payload = signal_panel_repo.SignalPanelRepository(db, user_id).panel_payload()
    return payload.model_dump() if isinstance(payload, BaseModel) else payload


def get_trading_risk(db: Session, user_id: str, args: dict[str, Any]) -> Any:
    config_key = args.get("config_key")
    prefs = trading_risk.load_trading_risk_prefs(db, user_id)
    board = strategy_board.load_strategy_board(db, user_id, config_key=str(config_key) if config_key else None)
    prefs_d = prefs.model_dump() if isinstance(prefs, BaseModel) else prefs
    raw_summary = dict(board.get("risk_summary") or {})
    return {"prefs": prefs_d, "risk_summary": raw_summary}

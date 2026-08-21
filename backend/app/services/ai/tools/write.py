"""投研写工具实现（需确认后落库，ai_tools 拆分）。"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any, cast

from sqlalchemy.orm import Session

from app.domains.content import notes
from app.domains.watchlist import positions_repo, signal_panel_repo
from app.domains.watchlist import repository as watchlist_repo
from app.services.ai.tools._common import ToolHandler
from app.services.symbols import to_vt_symbol

logger = logging.getLogger(__name__)

WRITE_TOOL_NAMES = frozenset(
    {
        "add_watchlist",
        "remove_watchlist",
        "upsert_note_memo",
        "add_note_entry",
        "upsert_position",
        "delete_position",
        "add_signal_panel",
        "remove_signal_panel",
    }
)


def _add_watchlist(db: Session, user_id: str, args: dict[str, Any]) -> Any:
    raw = str(args.get("symbol") or args.get("vt_symbol") or "").strip()
    if not raw:
        return {"error": "需要 symbol，例如 600519.SSE"}
    name = str(args.get("name") or "").strip()
    try:
        item = watchlist_repo.WatchlistItemRepository(db, user_id).add_item(
            raw_symbol=raw,
            name=name,
            exchange=args.get("exchange"),
        )
    except Exception as exc:
        return {"error": str(getattr(exc, "detail", None) or exc)}
    return {
        "ok": True,
        "vt_symbol": to_vt_symbol(item.symbol, item.exchange),
        "name": item.name or name,
        "symbol": item.symbol,
        "exchange": item.exchange,
    }


def _remove_watchlist(db: Session, user_id: str, args: dict[str, Any]) -> Any:
    raw = str(args.get("symbol") or args.get("vt_symbol") or "").strip()
    if not raw:
        return {"error": "需要 symbol，例如 600519.SSE"}
    try:
        symbol, exchange = watchlist_repo.resolve_symbol_pair(raw, args.get("exchange"))
    except Exception as exc:
        return {"error": f"标的解析失败：{exc}"}
    ok = watchlist_repo.WatchlistItemRepository(db, user_id).remove_item(symbol, exchange)
    if not ok:
        return {"error": "不在自选中"}
    # 尽量同步移出信号名单（忽略失败）
    try:
        panel = signal_panel_repo.SignalPanelRepository(db, user_id).load_symbols()
        vt = to_vt_symbol(symbol, exchange)
        if vt in panel:
            signal_panel_repo.SignalPanelRepository(db, user_id).save_symbols([s for s in panel if s != vt])
    except Exception:
        logger.warning("同步移出信号名单失败: vt=%s", to_vt_symbol(symbol, exchange), exc_info=True)
    return {"ok": True, "vt_symbol": to_vt_symbol(symbol, exchange), "removed": True}


def _upsert_note_memo(db: Session, user_id: str, args: dict[str, Any]) -> Any:
    raw = str(args.get("vt_symbol") or args.get("symbol") or "").strip()
    body = str(args.get("body") or "").strip()
    if not raw:
        return {"error": "需要 vt_symbol 或 symbol"}
    if not body:
        return {"error": "备忘内容 body 不能为空"}
    try:
        memo = notes.upsert_memo(db, user_id, raw, body)
    except Exception as exc:
        return {"error": str(getattr(exc, "detail", None) or exc)}
    return {
        "ok": True,
        "vt_symbol": memo.vt_symbol,
        "body_preview": (memo.body or "")[:120],
        "updated_at": memo.updated_at,
    }


def _add_note_entry(db: Session, user_id: str, args: dict[str, Any]) -> Any:
    raw = str(args.get("vt_symbol") or args.get("symbol") or "").strip()
    body = str(args.get("body") or "").strip()
    if not raw:
        return {"error": "需要 vt_symbol 或 symbol"}
    if not body:
        return {"error": "流水内容 body 不能为空"}
    try:
        entry = notes.add_entry(db, user_id, raw, body)
    except Exception as exc:
        return {"error": str(getattr(exc, "detail", None) or exc)}
    return {
        "ok": True,
        "id": entry.id,
        "vt_symbol": entry.vt_symbol,
        "body_preview": (entry.body or "")[:120],
        "created_at": entry.created_at,
    }


def _upsert_position(db: Session, user_id: str, args: dict[str, Any]) -> Any:
    raw = str(args.get("symbol") or args.get("vt_symbol") or "").strip()
    if not raw:
        return {"error": "需要 symbol，例如 600519.SSE"}
    try:
        cost_price = float(cast(Any, args.get("cost_price")))
        volume = int(cast(Any, args.get("volume")))
    except (TypeError, ValueError):
        return {"error": "cost_price / volume 无效"}
    buy_date = str(args.get("buy_date") or "").strip()
    if not buy_date:
        return {"error": "需要 buy_date（YYYY-MM-DD）"}
    notes_text = str(args.get("notes") or "")
    try:
        symbol, exchange = watchlist_repo.resolve_symbol_pair(raw, args.get("exchange"))
        existing = positions_repo.PositionRepository(db, user_id).get_position(symbol, exchange)
        if existing:
            row = positions_repo.PositionRepository(db, user_id).update_position(
                symbol=symbol,
                exchange=exchange,
                cost_price=cost_price,
                volume=volume,
                buy_date=buy_date,
                notes=notes_text,
            )
            action = "updated"
        else:
            row = positions_repo.PositionRepository(db, user_id).add_position(
                symbol=symbol,
                exchange=exchange,
                cost_price=cost_price,
                volume=volume,
                buy_date=buy_date,
                notes=notes_text,
            )
            action = "created"
    except Exception as exc:
        return {"error": str(getattr(exc, "detail", None) or exc)}
    vt = str(row.vt_symbol or to_vt_symbol(symbol, exchange))
    return {
        "ok": True,
        "action": action,
        "vt_symbol": vt,
        "cost_price": row.cost_price,
        "volume": row.volume,
        "buy_date": row.buy_date,
    }


def _delete_position(db: Session, user_id: str, args: dict[str, Any]) -> Any:
    raw = str(args.get("symbol") or args.get("vt_symbol") or "").strip()
    if not raw:
        return {"error": "需要 symbol，例如 600519.SSE"}
    try:
        symbol, exchange = watchlist_repo.resolve_symbol_pair(raw, args.get("exchange"))
        ok = positions_repo.PositionRepository(db, user_id).delete_position(symbol=symbol, exchange=exchange)
    except Exception as exc:
        return {"error": str(getattr(exc, "detail", None) or exc)}
    if not ok:
        return {"error": "持仓不存在"}
    return {"ok": True, "vt_symbol": to_vt_symbol(symbol, exchange), "removed": True}


def _add_signal_panel(db: Session, user_id: str, args: dict[str, Any]) -> Any:
    raw = str(args.get("symbol") or args.get("vt_symbol") or "").strip()
    if not raw:
        return {"error": "需要 symbol，例如 600519.SSE"}
    try:
        symbols = signal_panel_repo.SignalPanelRepository(db, user_id).add_symbol(raw)
    except Exception as exc:
        return {"error": str(getattr(exc, "detail", None) or exc)}
    return {"ok": True, "symbols": symbols}


def _remove_signal_panel(db: Session, user_id: str, args: dict[str, Any]) -> Any:
    raw = str(args.get("symbol") or args.get("vt_symbol") or "").strip()
    if not raw:
        return {"error": "需要 symbol，例如 600519.SSE"}
    try:
        symbols = signal_panel_repo.SignalPanelRepository(db, user_id).remove_symbol(raw)
    except Exception as exc:
        return {"error": str(getattr(exc, "detail", None) or exc)}
    return {"ok": True, "symbols": symbols}


_SummaryFn = Callable[[dict[str, Any]], str]


def _sym(args: dict[str, Any], *, vt_first: bool = False) -> str:
    first, second = ("vt_symbol", "symbol") if vt_first else ("symbol", "vt_symbol")
    return str(args.get(first) or args.get(second) or "").strip() or "?"


def _preview(raw: Any, limit: int = 40) -> str:
    body = str(raw or "").strip().replace("\n", " ")
    return body[:limit] + ("…" if len(body) > limit else "")


def _sum_add_watchlist(args: dict[str, Any]) -> str:
    name = str(args.get("name") or "").strip()
    suffix = f"（{name}）" if name else ""
    return f"加自选：{_sym(args)}{suffix}"


_WRITE_SUMMARIES: dict[str, _SummaryFn] = {
    "add_watchlist": _sum_add_watchlist,
    "remove_watchlist": lambda a: f"删自选：{_sym(a)}",
    "upsert_note_memo": lambda a: f"写备忘：{_sym(a, vt_first=True)} — {_preview(a.get('body'))}",
    "add_note_entry": lambda a: f"记流水：{_sym(a, vt_first=True)} — {_preview(a.get('body'))}",
    "upsert_position": lambda a: f"录入/更新持仓：{_sym(a)} 成本{a.get('cost_price')} 数量{a.get('volume')}",
    "delete_position": lambda a: f"删除持仓：{_sym(a)}",
    "add_signal_panel": lambda a: f"加入信号名单：{_sym(a)}",
    "remove_signal_panel": lambda a: f"移出信号名单：{_sym(a)}",
}


def summarize_write_tool(name: str, args: dict[str, Any]) -> str:
    fn = _WRITE_SUMMARIES.get(name)
    return fn(args) if fn else name


WRITE_HANDLERS: dict[str, ToolHandler] = {
    "add_watchlist": _add_watchlist,
    "remove_watchlist": _remove_watchlist,
    "upsert_note_memo": _upsert_note_memo,
    "add_note_entry": _add_note_entry,
    "upsert_position": _upsert_position,
    "delete_position": _delete_position,
    "add_signal_panel": _add_signal_panel,
    "remove_signal_panel": _remove_signal_panel,
}

WRITE_DEFINITIONS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "add_watchlist",
            "description": "提议将股票加入自选（需用户在界面确认后才生效）",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "如 600519.SSE / 000001 / SHSE.600519"},
                    "vt_symbol": {"type": "string"},
                    "name": {"type": "string", "description": "可选名称"},
                    "exchange": {"type": "string"},
                },
                "required": ["symbol"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "remove_watchlist",
            "description": "提议从自选中删除股票（需用户在界面确认后才生效）",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "如 600519.SSE"},
                    "vt_symbol": {"type": "string"},
                    "exchange": {"type": "string"},
                },
                "required": ["symbol"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "upsert_note_memo",
            "description": "提议写入或覆盖某票备忘录（需用户在界面确认后才生效）",
            "parameters": {
                "type": "object",
                "properties": {
                    "vt_symbol": {"type": "string", "description": "如 600519.SSE"},
                    "symbol": {"type": "string"},
                    "body": {"type": "string", "description": "备忘全文"},
                },
                "required": ["body"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_note_entry",
            "description": "提议追加一条股票操作/观察流水（追加而非覆盖备忘；需用户确认）",
            "parameters": {
                "type": "object",
                "properties": {
                    "vt_symbol": {"type": "string", "description": "如 600519.SSE"},
                    "symbol": {"type": "string"},
                    "body": {"type": "string", "description": "流水全文"},
                },
                "required": ["body"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "upsert_position",
            "description": "提议录入或更新持仓（须先在自选；需用户确认后生效）",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string"},
                    "vt_symbol": {"type": "string"},
                    "exchange": {"type": "string"},
                    "cost_price": {"type": "number"},
                    "volume": {"type": "integer", "description": "100 股整手"},
                    "buy_date": {"type": "string", "description": "YYYY-MM-DD"},
                    "notes": {"type": "string"},
                },
                "required": ["symbol", "cost_price", "volume", "buy_date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_position",
            "description": "提议删除持仓（需用户确认后生效）",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string"},
                    "vt_symbol": {"type": "string"},
                    "exchange": {"type": "string"},
                },
                "required": ["symbol"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_signal_panel",
            "description": "提议将股票加入信号名单（需用户确认后生效）",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string"},
                    "vt_symbol": {"type": "string"},
                },
                "required": ["symbol"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "remove_signal_panel",
            "description": "提议将股票移出信号名单（需用户确认后生效）",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string"},
                    "vt_symbol": {"type": "string"},
                },
                "required": ["symbol"],
            },
        },
    },
]

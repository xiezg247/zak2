"""投研工具：只读 + 需确认的写操作，供 Agent tool-calling。"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from typing import Any

from sqlalchemy.orm import Session

from app.repositories import backtest as backtest_repo
from app.repositories import positions as positions_repo
from app.repositories import signal_panel as signal_panel_repo
from app.repositories import watchlist as watchlist_repo
from app.services import bars, notes
from app.services.symbols import to_vt_symbol

logger = logging.getLogger(__name__)

MAX_RESULT_CHARS = 6000

ToolHandler = Callable[[Session, str, dict[str, Any]], Any]

WRITE_TOOL_NAMES = frozenset({
    "add_watchlist",
    "remove_watchlist",
    "upsert_note_memo",
    "add_note_entry",
    "upsert_position",
    "delete_position",
    "add_signal_panel",
    "remove_signal_panel",
})



def _truncate(payload: Any) -> str:
    text = json.dumps(payload, ensure_ascii=False, default=str)
    if len(text) <= MAX_RESULT_CHARS:
        return text
    return text[: MAX_RESULT_CHARS - 20] + "…(truncated)"


def _get_watchlist(db: Session, user_id: str, args: dict[str, Any]) -> Any:
    from app.services import ai_read_tools

    return ai_read_tools.get_watchlist(db, user_id, args)


def _get_positions(db: Session, user_id: str, args: dict[str, Any]) -> Any:
    from app.services import ai_read_tools

    return ai_read_tools.get_positions(db, user_id, args)


def _get_signal_panel(db: Session, user_id: str, args: dict[str, Any]) -> Any:
    from app.services import ai_read_tools

    return ai_read_tools.get_signal_panel(db, user_id, args)


def _get_trading_risk(db: Session, user_id: str, args: dict[str, Any]) -> Any:
    from app.services import ai_read_tools

    return ai_read_tools.get_trading_risk(db, user_id, args)


def _get_market_emotion(db: Session, user_id: str, args: dict[str, Any]) -> Any:
    from app.services import ai_read_tools

    return ai_read_tools.get_market_emotion(db, user_id, args)


def _get_recent_screening(db: Session, user_id: str, args: dict[str, Any]) -> Any:
    from app.services import ai_read_tools

    return ai_read_tools.get_recent_screening(db, user_id, args)


def _get_radar_snapshot(db: Session, user_id: str, args: dict[str, Any]) -> Any:
    from app.services import ai_read_tools

    return ai_read_tools.get_radar_snapshot(db, user_id, args)


def _list_note_symbols(db: Session, user_id: str, args: dict[str, Any]) -> Any:
    from app.services import ai_read_tools

    return ai_read_tools.list_note_symbols(db, user_id, args)


def _get_stock_notes(db: Session, user_id: str, args: dict[str, Any]) -> Any:
    from app.services import ai_read_tools

    return ai_read_tools.get_stock_notes(db, user_id, args)


def _get_bars_summary(db: Session, user_id: str, args: dict[str, Any]) -> Any:
    _ = user_id
    raw = str(args.get("vt_symbol") or args.get("symbol") or "").strip()
    if not raw:
        return {"error": "需要 vt_symbol 或 symbol，例如 600519.SSE"}
    try:
        symbol, exchange = watchlist_repo.resolve_symbol_pair(raw, args.get("exchange"))
    except Exception as exc:  # noqa: BLE001
        return {"error": f"标的解析失败：{exc}"}
    limit = max(20, min(int(args.get("limit") or 60), 120))
    try:
        resp = bars.load_bars(db, symbol=symbol, exchange=exchange, interval="d", limit=limit)
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)}
    bar_rows = list(resp.bars or [])
    if not bar_rows:
        return {
            "vt_symbol": to_vt_symbol(symbol, exchange),
            "count": 0,
            "message": "无本地日 K，请先下载或补全日 K",
        }
    ordered = sorted(bar_rows, key=lambda b: b.datetime)
    first, last = ordered[0], ordered[-1]
    first_close = float(first.close)
    last_close = float(last.close)
    change_pct = ((last_close / first_close) - 1.0) * 100 if first_close else 0.0
    high = max(float(b.high) for b in ordered)
    low = min(float(b.low) for b in ordered)
    closes = [float(b.close) for b in ordered]
    return {
        "vt_symbol": to_vt_symbol(symbol, exchange),
        "count": len(ordered),
        "start": str(first.datetime),
        "end": str(last.datetime),
        "last_close": last_close,
        "period_change_pct": round(change_pct, 2),
        "high": high,
        "low": low,
        "avg_close": round(sum(closes) / len(closes), 3) if closes else 0,
        "tail": [
            {
                "datetime": str(b.datetime),
                "close": float(b.close),
                "volume": float(b.volume),
            }
            for b in ordered[-5:]
        ],
    }


def _get_recent_backtest(db: Session, user_id: str, args: dict[str, Any]) -> Any:
    limit = max(1, min(int(args.get("limit") or 5), 20))
    runs = backtest_repo.BacktestRepository(db, user_id).list_runs(limit=limit)
    return {
        "runs": [
            {
                "id": r.id,
                "vt_symbol": r.vt_symbol,
                "strategy": r.strategy,
                "start_date": r.start_date,
                "end_date": r.end_date,
                "total_return": r.total_return,
                "max_drawdown": r.max_drawdown,
                "sharpe_ratio": r.sharpe_ratio,
                "trade_count": r.trade_count,
                "created_at": r.created_at,
            }
            for r in runs
        ]
    }


def _list_skills(db: Session, user_id: str, args: dict[str, Any]) -> Any:
    _ = db, user_id, args
    from app.services import skills_catalog

    return {"skills": skills_catalog.list_skills()}


def _read_skill(db: Session, user_id: str, args: dict[str, Any]) -> Any:
    _ = db, user_id
    from app.services import skills_catalog

    sid = str(args.get("skill_id") or "").strip()
    try:
        return skills_catalog.read_skill(sid)
    except ValueError as exc:
        return {"error": str(exc)}


def _run_skill(db: Session, user_id: str, args: dict[str, Any]) -> Any:
    from app.services.skill_runtime import SkillContext, run_skill_module

    sid = str(args.get("skill_id") or "").strip()
    if not sid:
        return {"error": "缺少 skill_id"}
    payload = {k: v for k, v in args.items() if k != "skill_id"}
    return run_skill_module(sid, SkillContext(db=db, user_id=user_id), payload)


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
    except Exception as exc:  # noqa: BLE001
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
    except Exception as exc:  # noqa: BLE001
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
    except Exception:  # noqa: BLE001
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
    except Exception as exc:  # noqa: BLE001
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
    except Exception as exc:  # noqa: BLE001
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
        cost_price = float(args.get("cost_price"))
        volume = int(args.get("volume"))
    except (TypeError, ValueError):
        return {"error": "cost_price / volume 无效"}
    buy_date = str(args.get("buy_date") or "").strip()
    if not buy_date:
        return {"error": "需要 buy_date（YYYY-MM-DD）"}
    notes_text = str(args.get("notes") or "")
    plan_pct = args.get("plan_pct")
    if plan_pct is not None and plan_pct != "":
        try:
            plan_pct = float(plan_pct)
        except (TypeError, ValueError):
            return {"error": "plan_pct 无效"}
    else:
        plan_pct = None
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
                plan_pct=plan_pct,
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
                plan_pct=plan_pct,
            )
            action = "created"
    except Exception as exc:  # noqa: BLE001
        return {"error": str(getattr(exc, "detail", None) or exc)}
    vt = str(row.get("vt_symbol") or to_vt_symbol(symbol, exchange))
    return {
        "ok": True,
        "action": action,
        "vt_symbol": vt,
        "cost_price": row.get("cost_price"),
        "volume": row.get("volume"),
        "buy_date": row.get("buy_date"),
    }


def _delete_position(db: Session, user_id: str, args: dict[str, Any]) -> Any:
    raw = str(args.get("symbol") or args.get("vt_symbol") or "").strip()
    if not raw:
        return {"error": "需要 symbol，例如 600519.SSE"}
    try:
        symbol, exchange = watchlist_repo.resolve_symbol_pair(raw, args.get("exchange"))
        ok = positions_repo.PositionRepository(db, user_id).delete_position(symbol=symbol, exchange=exchange)
    except Exception as exc:  # noqa: BLE001
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
    except Exception as exc:  # noqa: BLE001
        return {"error": str(getattr(exc, "detail", None) or exc)}
    return {"ok": True, "symbols": symbols}


def _remove_signal_panel(db: Session, user_id: str, args: dict[str, Any]) -> Any:
    raw = str(args.get("symbol") or args.get("vt_symbol") or "").strip()
    if not raw:
        return {"error": "需要 symbol，例如 600519.SSE"}
    try:
        symbols = signal_panel_repo.SignalPanelRepository(db, user_id).remove_symbol(raw)
    except Exception as exc:  # noqa: BLE001
        return {"error": str(getattr(exc, "detail", None) or exc)}
    return {"ok": True, "symbols": symbols}


def summarize_write_tool(name: str, args: dict[str, Any]) -> str:
    if name == "add_watchlist":
        sym = str(args.get("symbol") or args.get("vt_symbol") or "").strip() or "?"
        nm = str(args.get("name") or "").strip()
        return f"加自选：{sym}" + (f"（{nm}）" if nm else "")
    if name == "remove_watchlist":
        sym = str(args.get("symbol") or args.get("vt_symbol") or "").strip() or "?"
        return f"删自选：{sym}"
    if name == "upsert_note_memo":
        sym = str(args.get("vt_symbol") or args.get("symbol") or "").strip() or "?"
        body = str(args.get("body") or "").strip().replace("\n", " ")
        preview = body[:40] + ("…" if len(body) > 40 else "")
        return f"写备忘：{sym} — {preview}"
    if name == "add_note_entry":
        sym = str(args.get("vt_symbol") or args.get("symbol") or "").strip() or "?"
        body = str(args.get("body") or "").strip().replace("\n", " ")
        preview = body[:40] + ("…" if len(body) > 40 else "")
        return f"记流水：{sym} — {preview}"
    if name == "upsert_position":
        sym = str(args.get("symbol") or args.get("vt_symbol") or "").strip() or "?"
        cost = args.get("cost_price")
        vol = args.get("volume")
        return f"录入/更新持仓：{sym} 成本{cost} 数量{vol}"
    if name == "delete_position":
        sym = str(args.get("symbol") or args.get("vt_symbol") or "").strip() or "?"
        return f"删除持仓：{sym}"
    if name == "add_signal_panel":
        sym = str(args.get("symbol") or args.get("vt_symbol") or "").strip() or "?"
        return f"加入信号名单：{sym}"
    if name == "remove_signal_panel":
        sym = str(args.get("symbol") or args.get("vt_symbol") or "").strip() or "?"
        return f"移出信号名单：{sym}"
    return name


TOOL_HANDLERS: dict[str, ToolHandler] = {
    "get_watchlist": _get_watchlist,
    "get_positions": _get_positions,
    "get_signal_panel": _get_signal_panel,
    "get_trading_risk": _get_trading_risk,
    "get_market_emotion": _get_market_emotion,
    "get_recent_screening": _get_recent_screening,
    "get_radar_snapshot": _get_radar_snapshot,
    "list_note_symbols": _list_note_symbols,
    "get_stock_notes": _get_stock_notes,
    "get_bars_summary": _get_bars_summary,
    "get_recent_backtest": _get_recent_backtest,
    "list_skills": _list_skills,
    "read_skill": _read_skill,
    "run_skill": _run_skill,
}

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

TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "get_watchlist",
            "description": "获取当前用户自选池列表，可选附带最新行情涨跌幅",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "最多返回条数，默认 30"},
                    "with_quotes": {"type": "boolean", "description": "是否附带行情，默认 true"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_positions",
            "description": "获取当前用户记账持仓列表，可选附带最新行情",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "最多返回条数，默认 20，上限 20"},
                    "with_quotes": {"type": "boolean", "description": "是否附带行情，默认 true"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_signal_panel",
            "description": "获取当前用户自选信号名单（vt_symbol 列表）",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_trading_risk",
            "description": "获取交易风控偏好与仓位/计划外摘要（risk_summary）",
            "parameters": {
                "type": "object",
                "properties": {
                    "config_key": {
                        "type": "string",
                        "description": "可选策略 config_key，缺省与策略看盘一致",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_market_emotion",
            "description": "获取连板情绪与市场概览（最高连板、龙头等）",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_recent_screening",
            "description": "获取用户最近选股运行结果摘要与 Top 命中行",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "最近几次选股，默认 1"},
                    "top_n": {"type": "integer", "description": "每次返回前 N 行，默认 20"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_radar_snapshot",
            "description": "获取雷达卡片快照；可指定 card_id，否则返回全部卡片摘要",
            "parameters": {
                "type": "object",
                "properties": {
                    "card_id": {"type": "string", "description": "可选，如 sector_flow_hot"},
                    "max_rows": {"type": "integer", "description": "每卡最多行数，默认 15"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_note_symbols",
            "description": "列出用户有备忘或流水的股票标的（含预览与流水条数）",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "最多返回条数，默认 30"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_stock_notes",
            "description": "读取单票备忘全文与近期操作/观察流水",
            "parameters": {
                "type": "object",
                "properties": {
                    "vt_symbol": {"type": "string", "description": "如 600519.SSE 或 000001.SZSE"},
                    "symbol": {"type": "string"},
                    "entry_limit": {"type": "integer", "description": "流水条数，默认 20"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_bars_summary",
            "description": "获取单票本地日 K 摘要（区间涨跌、高低、最近收盘）",
            "parameters": {
                "type": "object",
                "properties": {
                    "vt_symbol": {"type": "string", "description": "如 600519.SSE 或 000001.SZSE"},
                    "symbol": {"type": "string"},
                    "exchange": {"type": "string"},
                    "limit": {"type": "integer", "description": "K 线根数，默认 60"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_recent_backtest",
            "description": "获取用户最近回测结果列表（收益、回撤、夏普）",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "默认 5"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_skills",
            "description": "列出内置投研 Skill 目录（id、名称、简介），按需再 read_skill 加载全文",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_skill",
            "description": "读取指定 skill 的 SKILL.md 全文（只读）",
            "parameters": {
                "type": "object",
                "properties": {
                    "skill_id": {"type": "string", "description": "如 watchlist、radar"},
                },
                "required": ["skill_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_skill",
            "description": "执行内置 skill 目录下 skill.py 的 run()（只读示范；超时约 5s）",
            "parameters": {
                "type": "object",
                "properties": {
                    "skill_id": {"type": "string", "description": "如 market-emotion"},
                },
                "required": ["skill_id"],
                "additionalProperties": True,
            },
        },
    },
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
                    "plan_pct": {"type": "number"},
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


def _mcp_tool_definitions() -> list[dict[str, Any]]:
    """白名单 MCP 工具 → OpenAI tools 定义；失败时静默为空。"""
    from app.services import mcp_client

    if not mcp_client.mcp_configured():
        return []
    try:
        tools = mcp_client.list_allowed_tools()
    except Exception:  # noqa: BLE001
        return []
    defs: list[dict[str, Any]] = []
    for tool in tools:
        schema = tool.input_schema or {"type": "object", "properties": {}}
        if not isinstance(schema, dict):
            schema = {"type": "object", "properties": {}}
        desc = tool.description or f"MCP 工具 {tool.name}"
        defs.append(
            {
                "type": "function",
                "function": {
                    "name": mcp_client.agent_tool_name(tool.name),
                    "description": f"[MCP] {desc}",
                    "parameters": schema,
                },
            }
        )
    return defs


def get_tool_definitions() -> list[dict[str, Any]]:
    """本地工具 +（可选）MCP 白名单工具。"""
    return [*TOOL_DEFINITIONS, *_mcp_tool_definitions()]


def _parse_args(arguments: dict[str, Any] | str | None) -> dict[str, Any]:
    if arguments is None:
        return {}
    if isinstance(arguments, str):
        try:
            parsed = json.loads(arguments or "{}")
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}
    if isinstance(arguments, dict):
        return arguments
    return {}


def execute_write_tool(db: Session, user_id: str, name: str, arguments: dict[str, Any] | str | None) -> Any:
    """仅由确认 API 调用；直接落库。"""
    handler = WRITE_HANDLERS.get(name)
    if not handler:
        return {"error": f"未知写工具：{name}"}
    args = _parse_args(arguments)
    try:
        return handler(db, user_id, args)
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)}


def _execute_mcp_tool(name: str, arguments: dict[str, Any] | str | None) -> str:
    from app.services import mcp_client

    remote = mcp_client.remote_tool_name(name)
    if not remote:
        return _truncate({"error": f"未知工具：{name}"})
    args = _parse_args(arguments)
    try:
        return mcp_client.call_allowed_tool(remote, args)
    except mcp_client.McpClientError as exc:
        return _truncate({"error": str(exc)})
    except Exception as exc:  # noqa: BLE001
        return _truncate({"error": str(exc)})


def execute_tool(db: Session, user_id: str, name: str, arguments: dict[str, Any] | str | None) -> str:
    if name in WRITE_TOOL_NAMES:
        return _truncate(
            {
                "error": "写操作须经用户确认，不能直接执行",
                "hint": "agent 应走 proposal 流程",
            }
        )
    if name.startswith("mcp_"):
        return _execute_mcp_tool(name, arguments)
    handler = TOOL_HANDLERS.get(name)
    if not handler:
        return _truncate({"error": f"未知工具：{name}"})
    args = _parse_args(arguments)
    try:
        result = handler(db, user_id, args)
    except Exception as exc:  # noqa: BLE001
        result = {"error": str(exc)}
    return _truncate(result)

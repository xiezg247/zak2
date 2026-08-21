"""投研只读工具实现（ai_tools 拆分）。"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.domains.backtest import repository as backtest_repo
from app.domains.market import bars
from app.domains.watchlist import repository as watchlist_repo
from app.services.symbols import to_vt_symbol
from app.services.ai.tools._common import ToolHandler


def _get_watchlist(db: Session, user_id: str, args: dict[str, Any]) -> Any:
    from app.services.ai import ai_read_tools

    return ai_read_tools.get_watchlist(db, user_id, args)


def _get_positions(db: Session, user_id: str, args: dict[str, Any]) -> Any:
    from app.services.ai import ai_read_tools

    return ai_read_tools.get_positions(db, user_id, args)


def _get_signal_panel(db: Session, user_id: str, args: dict[str, Any]) -> Any:
    from app.services.ai import ai_read_tools

    return ai_read_tools.get_signal_panel(db, user_id, args)


def _get_trading_risk(db: Session, user_id: str, args: dict[str, Any]) -> Any:
    from app.services.ai import ai_read_tools

    return ai_read_tools.get_trading_risk(db, user_id, args)


def _get_market_emotion(db: Session, user_id: str, args: dict[str, Any]) -> Any:
    from app.services.ai import ai_read_tools

    return ai_read_tools.get_market_emotion(db, user_id, args)


def _get_recent_screening(db: Session, user_id: str, args: dict[str, Any]) -> Any:
    from app.services.ai import ai_read_tools

    return ai_read_tools.get_recent_screening(db, user_id, args)


def _get_radar_snapshot(db: Session, user_id: str, args: dict[str, Any]) -> Any:
    from app.services.ai import ai_read_tools

    return ai_read_tools.get_radar_snapshot(db, user_id, args)


def _list_note_symbols(db: Session, user_id: str, args: dict[str, Any]) -> Any:
    from app.services.ai import ai_read_tools

    return ai_read_tools.list_note_symbols(db, user_id, args)


def _get_stock_notes(db: Session, user_id: str, args: dict[str, Any]) -> Any:
    from app.services.ai import ai_read_tools

    return ai_read_tools.get_stock_notes(db, user_id, args)


def _get_bars_summary(db: Session, user_id: str, args: dict[str, Any]) -> Any:
    _ = user_id
    raw = str(args.get("vt_symbol") or args.get("symbol") or "").strip()
    if not raw:
        return {"error": "需要 vt_symbol 或 symbol，例如 600519.SSE"}
    try:
        symbol, exchange = watchlist_repo.resolve_symbol_pair(raw, args.get("exchange"))
    except Exception as exc:
        return {"error": f"标的解析失败：{exc}"}
    limit = max(20, min(int(args.get("limit") or 60), 120))
    try:
        resp = bars.load_bars(db, symbol=symbol, exchange=exchange, interval="d", limit=limit)
    except Exception as exc:
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


READ_HANDLERS: dict[str, ToolHandler] = {
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
}

READ_DEFINITIONS: list[dict[str, Any]] = [
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
            "description": "获取交易风控偏好与仓位摘要（risk_summary）",
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
]

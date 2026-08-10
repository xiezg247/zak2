"""投研团队预取：日 K / 估值切片 / 情绪 / 信号。"""

from __future__ import annotations

import math
from typing import Any

from sqlalchemy.orm import Session

from app.services import emotion_cycle as emotion_cycle_svc
from app.services import strategy_board, watchlist_repo
from app.services.bars import load_bars
from app.services.quotes import get_quote_store
from app.services.symbols import to_tf_symbol, to_vt_symbol


def _volatility_and_dd(closes: list[float]) -> tuple[float | None, float | None]:
    if len(closes) < 5:
        return None, None
    rets: list[float] = []
    for i in range(1, len(closes)):
        if closes[i - 1] > 0:
            rets.append(closes[i] / closes[i - 1] - 1.0)
    vol = None
    if len(rets) >= 2:
        mean = sum(rets) / len(rets)
        var = sum((r - mean) ** 2 for r in rets) / (len(rets) - 1)
        vol = round(math.sqrt(var) * math.sqrt(252) * 100, 2)

    peak = closes[0]
    max_dd = 0.0
    for c in closes:
        peak = max(peak, c)
        if peak > 0:
            max_dd = max(max_dd, (peak - c) / peak * 100)
    return vol, round(max_dd, 2)


def _ma_alignment(closes: list[float]) -> str:
    if len(closes) < 20:
        return ""
    ma5 = sum(closes[-5:]) / 5
    ma10 = sum(closes[-10:]) / 10
    ma20 = sum(closes[-20:]) / 20
    last = closes[-1]
    if last >= ma5 >= ma10 >= ma20:
        return "均线多头排列"
    if last <= ma5 <= ma10 <= ma20:
        return "均线空头排列"
    return "均线纠缠"


def _try_valuation(symbol: str, exchange: str) -> dict[str, Any]:
    """尽力从 Tushare daily_basic 取单票估值；失败则空 dict。"""
    try:
        from app.services import tushare_client as ts

        token = ""
        try:
            token = ts.require_token()
        except Exception:  # noqa: BLE001
            return {}
        _ = token
        exch = exchange.upper()
        if exch in {"SSE", "SHSE"}:
            ts_code = f"{symbol}.SH"
        elif exch in {"SZSE", "SZ"}:
            ts_code = f"{symbol}.SZ"
        elif exch in {"BSE", "BJSE"}:
            ts_code = f"{symbol}.BJ"
        else:
            ts_code = f"{symbol}.SH"

        from datetime import datetime, timedelta, timezone

        china = timezone(timedelta(hours=8))
        day = datetime.now(china)
        for _ in range(8):
            trade_date = day.strftime("%Y%m%d")
            try:
                rows = ts.query(
                    "daily_basic",
                    {"ts_code": ts_code, "trade_date": trade_date},
                    fields="ts_code,trade_date,pe_ttm,pb,total_mv",
                )
            except Exception:  # noqa: BLE001
                rows = []
            if rows:
                item = rows[0]
                pe = ts.safe_float(item.get("pe_ttm"))
                pb = ts.safe_float(item.get("pb"))
                mv = ts.safe_float(item.get("total_mv"))
                return {
                    "pe_ttm": pe if pe > 0 else None,
                    "pb": pb if pb > 0 else None,
                    "total_mv_yi": round(mv / 10000.0, 2) if mv else None,
                    "trade_date": trade_date,
                    "source": "tushare_daily_basic",
                }
            day -= timedelta(days=1)
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)}
    return {}


def prefetch_team(db: Session, user_id: str, raw_symbol: str) -> dict[str, Any]:
    try:
        symbol, exchange = watchlist_repo.resolve_symbol_pair(raw_symbol)
    except Exception as exc:  # noqa: BLE001
        return {"error": f"标的解析失败：{exc}", "vt_symbol": raw_symbol}

    vt = to_vt_symbol(symbol, exchange)
    name = ""
    last_price = None
    change_pct = None

    store = get_quote_store()
    if store.available():
        tf = to_tf_symbol(symbol, exchange)
        quotes = store.get_quotes([tf])
        if quotes:
            q = quotes[0]
            name = q.name or ""
            last_price = q.last_price
            change_pct = q.change_pct

    # 日 K
    bars_payload: dict[str, Any] = {}
    closes: list[float] = []
    try:
        resp = load_bars(db, symbol=symbol, exchange=exchange, interval="d", limit=90)
        ordered = sorted(resp.bars or [], key=lambda b: b.datetime)
        closes = [float(b.close) for b in ordered]
        if closes:
            first, last = closes[0], closes[-1]
            period_change = ((last / first) - 1.0) * 100 if first else 0.0
            bars_payload = {
                "count": len(closes),
                "last_close": last,
                "period_change_pct": round(period_change, 2),
                "high": max(float(b.high) for b in ordered),
                "low": min(float(b.low) for b in ordered),
            }
    except Exception as exc:  # noqa: BLE001
        bars_payload = {"error": str(exc)}

    vol, dd = _volatility_and_dd(closes)
    ret_60 = None
    if len(closes) >= 60 and closes[-60] > 0:
        ret_60 = round((closes[-1] / closes[-60] - 1.0) * 100, 2)
    elif len(closes) >= 2 and closes[0] > 0:
        ret_60 = round((closes[-1] / closes[0] - 1.0) * 100, 2)

    emotion = emotion_cycle_svc.build_emotion_cycle(db)
    fg = (emotion.get("inputs") or {}).get("fear_greed_index")

    # 信号
    signal = "na"
    signal_label = "—"
    try:
        board = strategy_board.load_strategy_board(db, user_id)
        for row in board.get("signals") or []:
            if row.get("vt_symbol") == vt:
                signal = str(row.get("signal") or "na")
                signal_label = str(row.get("signal_label") or "—")
                break
    except Exception:  # noqa: BLE001
        pass

    valuation = _try_valuation(symbol, exchange)
    financial: dict[str, Any] = {**valuation}
    if not financial:
        financial = {"note": "无 Tushare 估值，财务分仅作占位"}

    risk = {
        "volatility_annualized_pct": vol,
        "max_drawdown_pct": dd,
        "return_pct_60d": ret_60,
        "fear_greed_index": fg,
    }
    if bars_payload.get("error"):
        risk["error"] = bars_payload["error"]

    strategy = {
        "ma_alignment": _ma_alignment(closes) if closes else "",
        "signal": signal,
        "signal_label": signal_label,
        "period_change_pct": bars_payload.get("period_change_pct"),
        "emotion_stage": emotion.get("stage"),
        "emotion_stage_label": emotion.get("stage_label"),
        "allow_new_positions": emotion.get("allow_new_positions"),
    }

    return {
        "vt_symbol": vt,
        "symbol": symbol,
        "exchange": exchange,
        "name": name,
        "last_price": last_price,
        "change_pct": change_pct,
        "bars": bars_payload,
        "financial": financial,
        "risk": risk,
        "strategy": strategy,
        "emotion": {
            "stage": emotion.get("stage"),
            "stage_label": emotion.get("stage_label"),
            "warnings": emotion.get("warnings") or [],
            "allow_new_positions": emotion.get("allow_new_positions"),
            "fear_greed_index": fg,
        },
    }

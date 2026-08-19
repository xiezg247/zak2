"""休市 / Redis 无行情时的数据库收盘排行回退。

数据源：
- public.dbbardata 日K（现价 / 前收 / 成交额）
- app.tushare_factor_cache.daily_basic（换手率 / 量比）
- app.limit_list_daily（连板）
- app.universe（名称）

各单位与 Redis 行情对齐：
- 成交额 → 元（Tushare daily.amount 为千元，×1000）
- 涨幅 / 换手率 → %（与 TickFlow 采集口径一致）
"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.schemas.market import RankRow
from app.services.market.tushare_screener import ts_code_to_tf
from app.services.symbols import normalize_exchange, to_tf_symbol, to_vt_symbol

# Tushare daily.amount 单位：千元 → 元
_QIANYUAN_TO_YUAN = 1000.0

# 可回退排序的排行字段（市场页 tabs 用到）
DB_RANKABLE_FIELDS = ("change_pct", "turnover_rate", "amount", "volume_ratio", "limit_times", "volume")


def _f(raw: Any, default: float = 0.0) -> float:
    if raw is None or raw == "":
        return default
    try:
        return float(raw)
    except (TypeError, ValueError):
        return default


def _latest_trade_dates(db: Session) -> tuple[str, str]:
    """返回日K最新两个交易日 (latest, prev)；无数据返回 ("", "")。"""
    rows = (
        db.execute(
            text(
                """
                SELECT DISTINCT datetime::date AS d
                FROM public.dbbardata
                WHERE interval = 'd'
                ORDER BY d DESC
                LIMIT 2
                """
            )
        )
        .mappings()
        .all()
    )
    dates = [str(r["d"]) for r in rows]
    if not dates:
        return "", ""
    return dates[0], dates[1] if len(dates) > 1 else ""


def _load_daily_bars(db: Session, trade_date: str) -> dict[str, dict[str, Any]]:
    """tf_symbol -> {symbol, exchange, last_price, open_price, high_price, low_price, amount, volume}。"""
    if not trade_date:
        return {}
    rows = (
        db.execute(
            text(
                """
                SELECT symbol, exchange, open_price, high_price, low_price, close_price, turnover, volume
                FROM public.dbbardata
                WHERE interval = 'd' AND datetime::date = :d
                """
            ),
            {"d": trade_date},
        )
        .mappings()
        .all()
    )
    out: dict[str, dict[str, Any]] = {}
    for r in rows:
        tf = to_tf_symbol(str(r["symbol"]), str(r["exchange"]))
        out[tf] = {
            "symbol": str(r["symbol"]),
            "exchange": normalize_exchange(str(r["exchange"])),
            "last_price": _f(r["close_price"]),
            "open_price": _f(r["open_price"]),
            "high_price": _f(r["high_price"]),
            "low_price": _f(r["low_price"]),
            "amount": _f(r["turnover"]) * _QIANYUAN_TO_YUAN,
            "volume": _f(r["volume"]),
        }
    return out


def _load_prev_closes(db: Session, trade_date: str) -> dict[str, float]:
    """tf_symbol -> 前收价。"""
    if not trade_date:
        return {}
    rows = (
        db.execute(
            text(
                """
                SELECT symbol, exchange, close_price
                FROM public.dbbardata
                WHERE interval = 'd' AND datetime::date = :d
                """
            ),
            {"d": trade_date},
        )
        .mappings()
        .all()
    )
    return {to_tf_symbol(str(r["symbol"]), str(r["exchange"])): _f(r["close_price"]) for r in rows}


def _load_daily_basic_factors(db: Session) -> dict[str, dict[str, float]]:
    """tf_symbol -> {turnover_rate, volume_ratio, total_mv, circ_mv}。"""
    payload = db.execute(
        text(
            """
            SELECT payload FROM app.tushare_factor_cache
            WHERE dataset = 'daily_basic'
            ORDER BY trade_date DESC
            LIMIT 1
            """
        )
    ).scalar()
    if not payload:
        return {}
    try:
        rows = json.loads(payload)
    except json.JSONDecodeError:
        return {}
    if not isinstance(rows, list):
        return {}
    out: dict[str, dict[str, float]] = {}
    for item in rows:
        if not isinstance(item, dict):
            continue
        tf = ts_code_to_tf(str(item.get("ts_code") or ""))
        if not tf or "." not in tf:
            continue
        out[tf] = {
            "turnover_rate": _f(item.get("turnover_rate")),
            "volume_ratio": _f(item.get("volume_ratio")),
            "total_mv": _f(item.get("total_mv")),
            "circ_mv": _f(item.get("circ_mv")),
        }
    return out


def _load_limit_times(db: Session, trade_date: str) -> dict[str, float]:
    """tf_symbol -> limit_times（当日涨停列表）。"""
    if not trade_date:
        return {}
    td = trade_date.replace("-", "")[:8]
    rows = (
        db.execute(
            text(
                """
                SELECT vt_symbol, limit_times FROM app.limit_list_daily
                WHERE trade_date = :td
                """
            ),
            {"td": td},
        )
        .mappings()
        .all()
    )
    return {str(r["vt_symbol"]): _f(r["limit_times"]) for r in rows}


def _load_names(db: Session) -> dict[str, str]:
    """tf_symbol -> name。"""
    rows = db.execute(
        text("SELECT symbol, exchange, name FROM app.universe WHERE name <> ''")
    ).mappings().all()
    return {to_tf_symbol(str(r["symbol"]), str(r["exchange"])): str(r["name"]) for r in rows}


def _load_industries(db: Session) -> dict[str, str]:
    """tf_symbol -> industry（申万行业 L2；缺失留空）。"""
    rows = db.execute(
        text(
            """
            SELECT symbol, exchange, industry
            FROM app.stock_industry
            WHERE industry <> ''
            """
        )
    ).mappings().all()
    return {
        to_tf_symbol(str(r["symbol"]), str(r["exchange"])): str(r["industry"]) for r in rows
    }


def db_rank_fallback(db: Session, field: str, *, top_n: int = 50) -> list[RankRow]:
    """从数据库构造收盘排行；无数据返回空列表（不抛错）。"""
    if field not in DB_RANKABLE_FIELDS:
        return []

    latest, prev = _latest_trade_dates(db)
    if not latest:
        return []

    bars = _load_daily_bars(db, latest)
    if not bars:
        return []

    prev_closes = _load_prev_closes(db, prev)
    factors = _load_daily_basic_factors(db)
    limit_times = _load_limit_times(db, latest)
    names = _load_names(db)
    industries = _load_industries(db)

    rows: list[RankRow] = []
    for tf, bar in bars.items():
        last_price = bar["last_price"]
        prev_close = prev_closes.get(tf, 0.0)
        change_pct = (last_price - prev_close) / prev_close * 100 if prev_close > 0 else 0.0
        change_amount = last_price - prev_close
        f = factors.get(tf, {})
        turnover_rate = f.get("turnover_rate", 0.0)
        volume_ratio = f.get("volume_ratio", 0.0)
        total_mv = f.get("total_mv", 0.0)
        circ_mv = f.get("circ_mv", 0.0)
        lt = limit_times.get(tf, 0.0)
        amount = bar["amount"]
        volume = bar["volume"]
        high = bar["high_price"]
        low = bar["low_price"]
        amplitude = (high - low) / prev_close * 100 if prev_close > 0 and high > 0 else 0.0

        score = {
            "change_pct": change_pct,
            "turnover_rate": turnover_rate,
            "amount": amount,
            "volume_ratio": volume_ratio,
            "limit_times": lt,
            "volume": volume,
        }.get(field, 0.0)

        rows.append(
            RankRow(
                rank=0,
                symbol=bar["symbol"],
                exchange=bar["exchange"],
                vt_symbol=to_vt_symbol(bar["symbol"], bar["exchange"]),
                tf_symbol=tf,
                name=names.get(tf, ""),
                score=score,
                last_price=last_price,
                change_pct=change_pct,
                change_amount=change_amount,
                prev_close=prev_close if prev_close > 0 else None,
                open_price=bar["open_price"] if bar["open_price"] > 0 else None,
                high_price=high if high > 0 else None,
                low_price=low if low > 0 else None,
                turnover_rate=turnover_rate,
                amount=amount,
                volume=volume,
                amplitude=amplitude,
                volume_ratio=volume_ratio,
                limit_times=lt,
                industry=industries.get(tf, ""),
                total_mv=total_mv if total_mv > 0 else None,
                circ_mv=circ_mv if circ_mv > 0 else None,
            )
        )

    rows.sort(key=lambda r: r.score, reverse=True)
    for i, row in enumerate(rows[:top_n], start=1):
        row.rank = i
    return rows[:top_n]

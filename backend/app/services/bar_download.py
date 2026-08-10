"""Tushare 日 K 下载写入 public.dbbardata / dbbaroverview（不依赖 vnpy）。"""

from __future__ import annotations

import os
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services import tushare_client as ts
from app.services.symbols import normalize_exchange, parse_flexible_symbol
from app.services.tushare_screener import latest_open_yyyymmdd

INTERVAL_DAILY = "d"
DEFAULT_MISSING_LOOKBACK_DAYS = 365
DEFAULT_UNIVERSE_START = date(2020, 1, 1)


def parse_universe_start(raw: str | None = None) -> date:
    """解析全市场日 K 统一起点；非法值回退 DEFAULT_UNIVERSE_START。"""
    text_v = (raw if raw is not None else os.getenv("BARS_UNIVERSE_START", "")).strip()
    if not text_v:
        return DEFAULT_UNIVERSE_START
    try:
        return date.fromisoformat(text_v)
    except ValueError:
        return DEFAULT_UNIVERSE_START


def list_universe_symbols(db: Session) -> list[tuple[str, str]]:
    rows = db.execute(
        text(
            """
            SELECT symbol, exchange
            FROM app.universe
            WHERE symbol IS NOT NULL AND exchange IS NOT NULL
            ORDER BY exchange, symbol
            """
        )
    ).mappings().all()
    return [(str(r["symbol"]), normalize_exchange(str(r["exchange"]))) for r in rows]


def select_universe_daily_targets(
    universe: list[tuple[str, str]],
    overview_starts: dict[tuple[str, str], date | None],
    *,
    unified_start: date,
) -> list[tuple[str, str]]:
    """筛选需首下日 K 的标的：无 overview、start 为空或晚于统一起点则纳入。"""
    out: list[tuple[str, str]] = []
    for key in universe:
        start = overview_starts.get(key)
        if start is None or start > unified_start:
            out.append(key)
    return out



def to_ts_code(symbol: str, exchange: str) -> str:
    code = symbol.strip()
    exch = normalize_exchange(exchange)
    suf = {"SSE": "SH", "SZSE": "SZ", "BSE": "BJ"}.get(exch, exch)
    return f"{code}.{suf}"


def parse_symbol_key(raw: str) -> tuple[str, str]:
    """任意风格代码 → (symbol, VeighNa exchange)。"""
    return parse_flexible_symbol(raw)


def as_of_trade_date(db: Session | None) -> date:
    ymd = latest_open_yyyymmdd(db)
    return date(int(ymd[:4]), int(ymd[4:6]), int(ymd[6:8]))


def overview_end_date(end_raw: Any) -> date | None:
    if end_raw is None:
        return None
    if isinstance(end_raw, datetime):
        return end_raw.date()
    if isinstance(end_raw, date):
        return end_raw
    text_v = str(end_raw).strip()
    if len(text_v) >= 10:
        return date.fromisoformat(text_v[:10])
    if len(text_v) == 8 and text_v.isdigit():
        return date(int(text_v[:4]), int(text_v[4:6]), int(text_v[6:8]))
    return None


def is_stale_end(end_raw: Any, *, as_of: date) -> bool:
    end_d = overview_end_date(end_raw)
    if end_d is None:
        return True
    return end_d < as_of


def get_overview_row(db: Session, *, symbol: str, exchange: str) -> dict[str, Any] | None:
    row = db.execute(
        text(
            """
            SELECT symbol, exchange, interval, start, "end", count
            FROM public.dbbaroverview
            WHERE symbol = :s AND exchange = :e AND interval = :iv
            """
        ),
        {"s": symbol, "e": normalize_exchange(exchange), "iv": INTERVAL_DAILY},
    ).mappings().first()
    return dict(row) if row else None


def list_stale_overviews(db: Session, *, as_of: date, limit: int) -> list[tuple[str, str, date | None]]:
    """返回 (symbol, exchange, end_date) 过期列表。"""
    limit = max(1, min(int(limit), 5000))
    rows = db.execute(
        text(
            """
            SELECT symbol, exchange, "end"
            FROM public.dbbaroverview
            WHERE interval = :iv
              AND exchange IS NOT NULL
              AND start IS NOT NULL
              AND "end" IS NOT NULL
              AND count > 0
              AND ("end")::date < :as_of
            ORDER BY ("end")::date ASC
            LIMIT :lim
            """
        ),
        {"iv": INTERVAL_DAILY, "as_of": as_of.isoformat(), "lim": limit},
    ).mappings().all()
    out: list[tuple[str, str, date | None]] = []
    for row in rows:
        out.append((str(row["symbol"]), normalize_exchange(str(row["exchange"])), overview_end_date(row["end"])))
    return out


def fetch_daily_rows(*, ts_code: str, start: date, end: date) -> list[dict[str, Any]]:
    return ts.query(
        "daily",
        {
            "ts_code": ts_code,
            "start_date": start.strftime("%Y%m%d"),
            "end_date": end.strftime("%Y%m%d"),
        },
        fields="ts_code,trade_date,open,high,low,close,vol,amount",
    )


def refresh_overview(db: Session, *, symbol: str, exchange: str) -> None:
    exch = normalize_exchange(exchange)
    stats = db.execute(
        text(
            """
            SELECT MIN(datetime) AS start_dt, MAX(datetime) AS end_dt, COUNT(*) AS n
            FROM public.dbbardata
            WHERE symbol = :s AND exchange = :e AND interval = :iv
            """
        ),
        {"s": symbol, "e": exch, "iv": INTERVAL_DAILY},
    ).mappings().first()
    db.execute(
        text(
            """
            DELETE FROM public.dbbaroverview
            WHERE symbol = :s AND exchange = :e AND interval = :iv
            """
        ),
        {"s": symbol, "e": exch, "iv": INTERVAL_DAILY},
    )
    if not stats or not stats["n"]:
        return
    db.execute(
        text(
            """
            INSERT INTO public.dbbaroverview (symbol, exchange, interval, start, "end", count)
            VALUES (:s, :e, :iv, :start, :end, :n)
            """
        ),
        {
            "s": symbol,
            "e": exch,
            "iv": INTERVAL_DAILY,
            "start": stats["start_dt"],
            "end": stats["end_dt"],
            "n": int(stats["n"]),
        },
    )


def upsert_daily_bars(
    db: Session,
    *,
    symbol: str,
    exchange: str,
    rows: list[dict[str, Any]],
) -> int:
    """写入日 K 行并刷新 overview；返回写入条数。"""
    if not rows:
        return 0
    exch = normalize_exchange(exchange)
    written = 0
    for row in rows:
        trade = str(row.get("trade_date") or "").strip()
        if len(trade) != 8 or not trade.isdigit():
            continue
        dt = datetime(int(trade[:4]), int(trade[4:6]), int(trade[6:8]))
        db.execute(
            text(
                """
                DELETE FROM public.dbbardata
                WHERE symbol = :s AND exchange = :e AND interval = :iv AND datetime = :dt
                """
            ),
            {"s": symbol, "e": exch, "iv": INTERVAL_DAILY, "dt": dt},
        )
        db.execute(
            text(
                """
                INSERT INTO public.dbbardata (
                    symbol, exchange, datetime, interval,
                    volume, turnover, open_interest,
                    open_price, high_price, low_price, close_price
                ) VALUES (
                    :s, :e, :dt, :iv,
                    :vol, :amt, 0,
                    :o, :h, :l, :c
                )
                """
            ),
            {
                "s": symbol,
                "e": exch,
                "dt": dt,
                "iv": INTERVAL_DAILY,
                "vol": ts.safe_float(row.get("vol")),
                "amt": ts.safe_float(row.get("amount")),
                "o": ts.safe_float(row.get("open")),
                "h": ts.safe_float(row.get("high")),
                "l": ts.safe_float(row.get("low")),
                "c": ts.safe_float(row.get("close")),
            },
        )
        written += 1
    if written:
        refresh_overview(db, symbol=symbol, exchange=exch)
    return written


def download_daily_bars(
    db: Session,
    *,
    symbol: str,
    exchange: str,
    start: date,
    end: date,
) -> int:
    """拉取并写入；无数据返回 0。"""
    if start > end:
        return 0
    ts_code = to_ts_code(symbol, exchange)
    rows = fetch_daily_rows(ts_code=ts_code, start=start, end=end)
    return upsert_daily_bars(db, symbol=symbol, exchange=exchange, rows=rows)


def resolve_fill_range(
    db: Session,
    *,
    symbol: str,
    exchange: str,
    as_of: date,
) -> tuple[date, date] | None:
    """返回需要补全的 [start, end]；已最新则 None。"""
    overview = get_overview_row(db, symbol=symbol, exchange=exchange)
    if overview is None:
        start = as_of - timedelta(days=DEFAULT_MISSING_LOOKBACK_DAYS)
        return start, as_of
    end_d = overview_end_date(overview.get("end"))
    if end_d is None or end_d < as_of:
        start = (end_d + timedelta(days=1)) if end_d else as_of - timedelta(days=DEFAULT_MISSING_LOOKBACK_DAYS)
        return start, as_of
    return None

"""Tushare 选股辅助（daily_basic / moneyflow）。"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, timedelta
from typing import Any, NamedTuple

from app.core.errors import AppError, Unavailable, UpstreamFailed
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.time import china_today
from app.domains.market import tushare_client as ts
from app.domains.market.quotes import QuoteRow

# daily_basic.total_mv 单位：万元；50 亿 = 500000 万
MIN_TOTAL_MV_50YI_WAN = 500_000.0


class LookbackFetch(NamedTuple):
    """_fetch_with_lookback 的返回：原始行 + 命中的交易日。"""

    raw: list[dict[str, Any]]
    trade_date: str


class QuoteScreenerResult(NamedTuple):
    """fetch_*_quote_rows 的返回：筛选结果 + 数据日期 + 扫描原始行数。"""

    rows: list[QuoteRow]
    trade_date: str
    scanned: int


def ts_code_to_tf(ts_code: str) -> str:
    text_v = str(ts_code or "").strip().upper()
    if "." not in text_v:
        return text_v
    code, suf = text_v.split(".", 1)
    mapping = {"SH": "SHSE", "SZ": "SZSE", "BJ": "BJSE"}
    return f"{mapping.get(suf, suf)}.{code}"


def latest_open_yyyymmdd(db: Session | None = None) -> str:
    if db is not None:
        cal = db.execute(
            text(
                """
                SELECT cal_date FROM app.trade_calendar
                WHERE is_open = 1 AND cal_date <= CURRENT_DATE::text
                ORDER BY cal_date DESC LIMIT 1
                """
            )
        ).scalar()
        if cal:
            return str(cal).replace("-", "")[:8]
    day = china_today()
    while day.weekday() >= 5:
        day -= timedelta(days=1)
    return day.strftime("%Y%m%d")


def _require_token() -> None:
    try:
        ts.require_token()
    except ts.TushareNotConfiguredError as exc:
        raise Unavailable(str(exc)) from exc


def _iter_trade_dates(start_yyyymmdd: str, *, max_lookback: int) -> list[str]:
    day = date(int(start_yyyymmdd[:4]), int(start_yyyymmdd[4:6]), int(start_yyyymmdd[6:8]))
    out: list[str] = []
    for _ in range(max_lookback):
        out.append(day.strftime("%Y%m%d"))
        day -= timedelta(days=1)
        while day.weekday() >= 5:
            day -= timedelta(days=1)
    return out


def fetch_daily_basic_rows(trade_date: str) -> list[dict[str, Any]]:
    return ts.query(
        "daily_basic",
        {"trade_date": trade_date},
        fields="ts_code,trade_date,close,pe_ttm,pb,total_mv,circ_mv,turnover_rate,volume_ratio",
    )


def fetch_moneyflow_rows(trade_date: str) -> list[dict[str, Any]]:
    return ts.query(
        "moneyflow",
        {"trade_date": trade_date},
        fields="ts_code,trade_date,buy_lg_amount,sell_lg_amount,buy_elg_amount,sell_elg_amount,net_mf_amount",
    )


def _basic_to_row(item: dict[str, Any]) -> QuoteRow | None:
    tf = ts_code_to_tf(str(item.get("ts_code") or ""))
    if not tf or "." not in tf:
        return None
    row = QuoteRow(
        symbol=tf,
        name="",
        last_price=ts.safe_float(item.get("close")),
        change_pct=0.0,
        turnover_rate=ts.safe_float(item.get("turnover_rate")),
        volume_ratio=ts.safe_float(item.get("volume_ratio")),
        total_mv=ts.safe_float(item.get("total_mv")),
        circ_mv=ts.safe_float(item.get("circ_mv")),
    )
    pe = ts.safe_float(item.get("pe_ttm"))
    if pe:
        row.__dict__["_pe_ttm"] = round(pe, 4)
    pb = ts.safe_float(item.get("pb"))
    if pb:
        row.__dict__["_pb"] = round(pb, 4)
    return row


def _fetch_with_lookback(
    db: Session | None,
    fetcher: Callable[[str], Any],
    *,
    max_lookback: int = 8,
    empty_detail: str,
) -> LookbackFetch:
    _require_token()
    last_error = ""
    for trade_date in _iter_trade_dates(latest_open_yyyymmdd(db), max_lookback=max_lookback):
        try:
            raw = fetcher(trade_date)
        except AppError as exc:
            last_error = str(exc.detail)
            raw = []
        if raw:
            return LookbackFetch(raw, trade_date)
    raise UpstreamFailed(last_error or empty_detail)


def fetch_low_pe_quote_rows(
    db: Session | None,
    *,
    max_pe: float = 15.0,
    max_lookback: int = 8,
) -> QuoteScreenerResult:
    raw, trade_date = _fetch_with_lookback(
        db,
        fetch_daily_basic_rows,
        max_lookback=max_lookback,
        empty_detail="Tushare daily_basic 无数据（可能积分不足或非交易日）",
    )
    rows: list[QuoteRow] = []
    for item in raw:
        pe = ts.safe_float(item.get("pe_ttm"))
        if pe <= 0 or pe >= max_pe:
            continue
        row = _basic_to_row(item)
        if row is None:
            continue
        row.__dict__["_pe_ttm"] = round(pe, 4)
        rows.append(row)
    rows.sort(key=lambda r: float(r.__dict__.get("_pe_ttm") or 99))
    return QuoteScreenerResult(rows, trade_date, len(raw))


def fetch_large_cap_quote_rows(
    db: Session | None,
    *,
    min_total_mv_wan: float = MIN_TOTAL_MV_50YI_WAN,
    max_lookback: int = 8,
) -> QuoteScreenerResult:
    raw, trade_date = _fetch_with_lookback(
        db,
        fetch_daily_basic_rows,
        max_lookback=max_lookback,
        empty_detail="Tushare daily_basic 无数据（可能积分不足或非交易日）",
    )
    rows: list[QuoteRow] = []
    for item in raw:
        mv = ts.safe_float(item.get("total_mv")) or ts.safe_float(item.get("circ_mv"))
        if mv < min_total_mv_wan:
            continue
        row = _basic_to_row(item)
        if row is None:
            continue
        rows.append(row)
    rows.sort(key=lambda r: r.total_mv or r.circ_mv, reverse=True)
    return QuoteScreenerResult(rows, trade_date, len(raw))


def fetch_moneyflow_in_quote_rows(
    db: Session | None,
    *,
    max_lookback: int = 8,
) -> QuoteScreenerResult:
    """主力净流入：moneyflow.net_mf_amount > 0 降序（单位通常为万元）。"""
    raw, trade_date = _fetch_with_lookback(
        db,
        fetch_moneyflow_rows,
        max_lookback=max_lookback,
        empty_detail="Tushare moneyflow 无数据（可能积分不足或非交易日）",
    )
    rows: list[QuoteRow] = []
    for item in raw:
        # net_mf_amount：部分接口为万元；也尝试大单净额估算
        net = ts.safe_float(item.get("net_mf_amount"))
        if net == 0:
            buy = ts.safe_float(item.get("buy_lg_amount")) + ts.safe_float(item.get("buy_elg_amount"))
            sell = ts.safe_float(item.get("sell_lg_amount")) + ts.safe_float(item.get("sell_elg_amount"))
            net = buy - sell
        if net <= 0:
            continue
        tf = ts_code_to_tf(str(item.get("ts_code") or ""))
        if not tf or "." not in tf:
            continue
        row = QuoteRow(symbol=tf, name="", net_mf_amount=net)
        row.__dict__["_net_mf_wan"] = round(net, 2)
        rows.append(row)
    rows.sort(key=lambda r: r.net_mf_amount, reverse=True)
    return QuoteScreenerResult(rows, trade_date, len(raw))

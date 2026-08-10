"""标杆对标：同业 + 估值 + 近 5 日动量（Tushare，对齐桌面权重）。"""

from __future__ import annotations

import math
from collections import Counter
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.schemas.screener import HardFilterPrefs, ReferencePeerRequest
from app.services import stock_industry
from app.services.hard_filters import apply_hard_filters, resolve_hard_filter
from app.services.quotes import QuoteRow, get_quote_store
from app.services.symbols import parse_flexible_symbol, to_vt_symbol
from app.services import tushare_client as ts
from app.services.tushare_screener import (
    _fetch_with_lookback,
    _iter_trade_dates,
    fetch_daily_basic_rows,
    latest_open_yyyymmdd,
    ts_code_to_tf,
)

_WEIGHT_INDUSTRY = 0.40
_WEIGHT_VALUATION = 0.35
_WEIGHT_MOMENTUM = 0.25
_MOMENTUM_DAYS = 5


def vt_to_ts_code(vt_symbol: str) -> str:
    code, exch = parse_flexible_symbol(vt_symbol)
    suf = {"SSE": "SH", "SZSE": "SZ", "BSE": "BJ"}.get(exch, "SH")
    return f"{code}.{suf}"


def tf_to_vt(tf_symbol: str) -> str:
    text = (tf_symbol or "").strip().upper()
    if "." not in text:
        return text
    left, right = text.split(".", 1)
    if left in {"SHSE", "SZSE", "BJSE"}:
        code, exch_raw = right, left
    else:
        code, exch_raw = left, right
    mapping = {"SHSE": "SSE", "SZSE": "SZSE", "BJSE": "BSE", "SSE": "SSE", "BSE": "BSE"}
    return to_vt_symbol(code, mapping.get(exch_raw, exch_raw))


def _positive_float(value: Any) -> float:
    try:
        number = float(value or 0)
    except (TypeError, ValueError):
        return 0.0
    return number if number > 0 else 0.0


def valuation_score(*, pe: float, mv: float, ref_pe: float, ref_mv: float) -> float:
    parts: list[float] = []
    if pe > 0 and ref_pe > 0:
        parts.append(min(abs(math.log(pe) - math.log(ref_pe)), 2.0) / 2.0)
    if mv > 0 and ref_mv > 0:
        parts.append(min(abs(math.log(mv) - math.log(ref_mv)), 2.0) / 2.0)
    if not parts:
        return 50.0
    distance = sum(parts) / len(parts)
    return round(max(0.0, (1.0 - distance) * 100), 1)


def momentum_score(reference: float, candidate: float) -> float:
    diff = abs(reference - candidate)
    return round(max(0.0, 100.0 - min(diff, 40.0) * 2.5), 1)


def cumulative_return(ts_code: str, pct_maps: list[dict[str, float]]) -> float:
    if not ts_code:
        return 0.0
    compound = 1.0
    for mapping in pct_maps:
        pct = float(mapping.get(ts_code, 0) or 0)
        compound *= 1.0 + pct / 100.0
    return (compound - 1.0) * 100.0


def composite_similarity(*, val_score: float, mom_score: float) -> float:
    industry_score = 100.0
    return round(
        industry_score * _WEIGHT_INDUSTRY + val_score * _WEIGHT_VALUATION + mom_score * _WEIGHT_MOMENTUM,
        1,
    )


def _fetch_industry_name_map() -> dict[str, dict[str, str]]:
    """ts_code → {industry, name}。"""
    rows = ts.query(
        "stock_basic",
        {"list_status": "L"},
        fields="ts_code,name,industry",
    )
    out: dict[str, dict[str, str]] = {}
    for row in rows:
        code = str(row.get("ts_code") or "").strip().upper()
        if not code:
            continue
        out[code] = {
            "industry": str(row.get("industry") or "").strip(),
            "name": str(row.get("name") or "").strip(),
        }
    return out


def _fetch_pct_maps(db: Session | None, *, days: int = _MOMENTUM_DAYS) -> list[dict[str, float]]:
    maps: list[dict[str, float]] = []
    for trade_date in _iter_trade_dates(latest_open_yyyymmdd(db), max_lookback=days + 4):
        try:
            raw = ts.query(
                "daily",
                {"trade_date": trade_date},
                fields="ts_code,pct_chg",
            )
        except HTTPException:
            continue
        if not raw:
            continue
        mapping: dict[str, float] = {}
        for item in raw:
            code = str(item.get("ts_code") or "").strip().upper()
            if code:
                mapping[code] = ts.safe_float(item.get("pct_chg"))
        if mapping:
            maps.append(mapping)
        if len(maps) >= days:
            break
    return maps


def _industry_dist_from_packed(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counter = Counter(str(r.get("industry") or "未知") for r in rows)
    total = sum(counter.values()) or 1
    return [
        {"industry": name, "count": count, "ratio": round(count / total, 4)}
        for name, count in counter.most_common()
    ]


def _enrich_from_redis(rows: list[QuoteRow]) -> None:
    store = get_quote_store()
    if not rows or not store.available():
        return
    try:
        quotes = store.get_quotes([r.symbol for r in rows[:200]])
    except Exception:  # noqa: BLE001
        return
    by_sym = {q.symbol: q for q in quotes}
    for row in rows:
        q = by_sym.get(row.symbol)
        if not q:
            continue
        if q.name and not row.name:
            row.name = q.name
        if q.change_pct:
            row.change_pct = q.change_pct
        if q.last_price:
            row.last_price = q.last_price
        if q.industry and not row.industry:
            row.industry = q.industry


def run_reference_peer(
    req: ReferencePeerRequest,
    *,
    db: Session | None = None,
    previous_symbols: set[str] | None = None,
) -> dict[str, Any]:
    try:
        ts.require_token()
    except ts.TushareNotConfiguredError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    try:
        ref_ts = vt_to_ts_code(req.vt_symbol)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    prefs = resolve_hard_filter(req.hard_filter, req.hard_filter_template)
    raw, trade_date = _fetch_with_lookback(
        db,
        fetch_daily_basic_rows,
        max_lookback=8,
        empty_detail="Tushare daily_basic 无数据（可能积分不足或非交易日）",
    )
    meta = _fetch_industry_name_map()
    by_ts = {str(item.get("ts_code") or "").strip().upper(): item for item in raw}
    reference = by_ts.get(ref_ts)
    if reference is None:
        raise HTTPException(status_code=404, detail=f"未找到标杆股 {req.vt_symbol} 的基本面数据")

    ref_meta = meta.get(ref_ts) or {}
    ref_industry = (ref_meta.get("industry") or "").strip()
    # Redis 行业兜底
    if not ref_industry:
        store = get_quote_store()
        if store.available():
            tf = ts_code_to_tf(ref_ts)
            quotes = store.get_quotes([tf])
            if quotes and quotes[0].industry:
                ref_industry = quotes[0].industry.strip()
    ref_name = (req.reference_name or "").strip() or ref_meta.get("name") or req.vt_symbol
    if not ref_industry or ref_industry == "未知":
        raise HTTPException(status_code=400, detail="标杆股缺少行业分类，暂无法做同业对标")

    candidates = [
        item
        for ts_code, item in by_ts.items()
        if ts_code != ref_ts and (meta.get(ts_code) or {}).get("industry") == ref_industry
    ]
    if not candidates:
        return {
            "condition": f"对标 · {ref_name}",
            "source": "reference_peer",
            "row_count": 0,
            "total_scanned": 0,
            "config": {
                **req.model_dump(),
                "trade_date": trade_date,
                "reference_industry": ref_industry,
                "hard_filter_resolved": prefs.model_dump(),
            },
            "rows": [],
            "industry_dist": [],
            "diff": {"added": [], "removed": [], "kept": []},
            "reference": {
                "vt_symbol": tf_to_vt(ts_code_to_tf(ref_ts)),
                "name": ref_name,
                "industry": ref_industry,
            },
        }

    pct_maps = _fetch_pct_maps(db, days=_MOMENTUM_DAYS)
    ref_pe = _positive_float(reference.get("pe_ttm") or reference.get("pe"))
    ref_mv = _positive_float(reference.get("circ_mv") or reference.get("total_mv"))
    ref_momentum = cumulative_return(ref_ts, pct_maps)

    scored_rows: list[QuoteRow] = []
    for item in candidates:
        ts_code = str(item.get("ts_code") or "").strip().upper()
        pe = _positive_float(item.get("pe_ttm") or item.get("pe"))
        mv = _positive_float(item.get("circ_mv") or item.get("total_mv"))
        val = valuation_score(pe=pe, mv=mv, ref_pe=ref_pe, ref_mv=ref_mv)
        mom = cumulative_return(ts_code, pct_maps)
        mom_s = momentum_score(ref_momentum, mom)
        sim = composite_similarity(val_score=val, mom_score=mom_s)
        tf = ts_code_to_tf(ts_code)
        name = (meta.get(ts_code) or {}).get("name") or ""
        reasons = [
            f"同业：{ref_industry}",
            f"估值：PE {pe:.1f} / 流通市值 {mv:,.0f} 万（标杆 PE {ref_pe:.1f} · {ref_mv:,.0f} 万）"
            if pe or mv
            else "估值：—",
            f"近{_MOMENTUM_DAYS}日涨跌 {mom:+.2f}%（标杆 {ref_momentum:+.2f}%）",
        ]
        row = QuoteRow(
            symbol=tf,
            name=name,
            last_price=ts.safe_float(item.get("close")),
            turnover_rate=ts.safe_float(item.get("turnover_rate")),
            volume_ratio=ts.safe_float(item.get("volume_ratio")),
            total_mv=ts.safe_float(item.get("total_mv")),
            circ_mv=ts.safe_float(item.get("circ_mv")),
            industry=ref_industry,
        )
        row.__dict__["_score"] = sim
        row.__dict__["_similarity_score"] = sim
        row.__dict__["_pe_ttm"] = round(pe, 4) if pe else None
        row.__dict__["_momentum_5d"] = round(mom, 2)
        row.__dict__["_hit_reason"] = "；".join(reasons[:2])
        row.__dict__["_pattern_hint"] = reasons[2] if len(reasons) > 2 else ""
        scored_rows.append(row)

    scored_rows.sort(key=lambda r: float(r.__dict__.get("_similarity_score") or 0), reverse=True)
    _enrich_from_redis(scored_rows)
    stock_industry.enrich_rows_from_db(db, scored_rows)
    ranked = apply_hard_filters(scored_rows, prefs)
    ranked = ranked[: req.top_n]

    packed: list[dict[str, Any]] = []
    for r in ranked:
        item = r.to_result_dict()
        item["vt_symbol"] = tf_to_vt(r.symbol)
        if r.total_mv > 0:
            item["total_mv_yi"] = round(r.total_mv / 10_000.0, 2)
        item["score"] = r.__dict__.get("_score")
        item["similarity_score"] = r.__dict__.get("_similarity_score")
        if r.__dict__.get("_pe_ttm") is not None:
            item["pe_ttm"] = r.__dict__["_pe_ttm"]
        item["momentum_5d"] = r.__dict__.get("_momentum_5d")
        item["hit_reason"] = r.__dict__.get("_hit_reason")
        item["pattern_hint"] = r.__dict__.get("_pattern_hint")
        item["reference_vt_symbol"] = tf_to_vt(ts_code_to_tf(ref_ts))
        packed.append(item)

    cur_syms = {r.symbol for r in ranked}
    if previous_symbols is None:
        diff = {"added": [], "removed": [], "kept": sorted(cur_syms)}
    else:
        diff = {
            "added": sorted(cur_syms - previous_symbols),
            "removed": sorted(previous_symbols - cur_syms),
            "kept": sorted(cur_syms & previous_symbols),
        }

    return {
        "condition": f"对标 · {ref_name}",
        "source": "reference_peer",
        "row_count": len(ranked),
        "total_scanned": len(candidates),
        "config": {
            **req.model_dump(),
            "trade_date": trade_date,
            "reference_industry": ref_industry,
            "hard_filter_resolved": prefs.model_dump(),
            "weights": {
                "industry": _WEIGHT_INDUSTRY,
                "valuation": _WEIGHT_VALUATION,
                "momentum": _WEIGHT_MOMENTUM,
            },
        },
        "rows": packed,
        "industry_dist": _industry_dist_from_packed(packed),
        "diff": diff,
        "reference": {
            "vt_symbol": tf_to_vt(ts_code_to_tf(ref_ts)),
            "name": ref_name,
            "industry": ref_industry,
            "momentum_5d": round(ref_momentum, 2),
            "pe_ttm": ref_pe or None,
        },
    }

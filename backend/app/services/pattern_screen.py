"""形态选股扫描：Redis 行情池 ∩ PG 日 K；theme_hot 仅行情。"""

from __future__ import annotations

from collections import Counter
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.bars import DbBarData
from app.schemas.screener import PatternRunRequest
from app.services import stock_industry
from app.services.hard_filters import apply_hard_filters, resolve_hard_filter
from app.services.pattern_rules import (
    PATTERN_META,
    QUOTE_ONLY_PATTERNS,
    BarSeries,
    get_matcher,
    is_known_pattern,
)
from app.services.quotes import QuoteRow, QuoteStore, get_quote_store
from app.services.suspend import load_suspended_vt_symbols
from app.services.symbols import normalize_exchange

_PATTERN_LABELS = {m["pattern_id"]: m["name"] for m in PATTERN_META}
_MIN_BARS = 60
_BAR_LIMIT = 100  # old_duck 需 ≥80


def list_patterns() -> list[dict[str, str]]:
    return [dict(m) for m in PATTERN_META]


def _parse_tf_symbol(tf_symbol: str) -> tuple[str, str] | None:
    """SHSE.600519 → (600519, SSE)。"""
    text = (tf_symbol or "").strip().upper()
    if "." not in text:
        return None
    left, right = text.split(".", 1)
    if left in {"SHSE", "SZSE", "BJSE", "SSE", "BSE"}:
        code, exch_raw = right, left
    else:
        code, exch_raw = left, right
    try:
        return code, normalize_exchange(exch_raw)
    except Exception:  # noqa: BLE001
        return None


def _load_bar_series_batch(
    db: Session,
    items: list[tuple[str, str]],
    *,
    limit: int = _BAR_LIMIT,
) -> dict[tuple[str, str], BarSeries]:
    """按 (symbol, exchange) 取日 K 尾部（每票最多 limit 根）。"""
    if not items:
        return {}
    uniq: list[tuple[str, str]] = list(dict.fromkeys(items))
    out: dict[tuple[str, str], BarSeries] = {}
    for symbol, exchange in uniq:
        stmt = (
            select(DbBarData)
            .where(
                DbBarData.symbol == symbol,
                DbBarData.exchange == exchange,
                DbBarData.interval == "d",
            )
            .order_by(DbBarData.datetime.desc())
            .limit(limit)
        )
        rows = list(db.scalars(stmt))
        if len(rows) < _MIN_BARS:
            continue
        rows.reverse()
        out[(symbol, exchange)] = BarSeries(
            closes=[float(r.close_price or 0) for r in rows],
            highs=[float(r.high_price or 0) for r in rows],
            lows=[float(r.low_price or 0) for r in rows],
            volumes=[float(r.volume or 0) for r in rows],
        )
    return out


def _industry_dist(rows: list[QuoteRow]) -> list[dict[str, Any]]:
    counter = Counter(r.industry or "未知" for r in rows)
    total = sum(counter.values()) or 1
    return [
        {"industry": name, "count": count, "ratio": round(count / total, 4)}
        for name, count in counter.most_common()
    ]


def _diff_symbols(current: list[QuoteRow], previous_symbols: set[str] | None) -> dict[str, Any]:
    if previous_symbols is None:
        return {"added": [], "removed": [], "kept": [r.symbol for r in current]}
    cur = {r.symbol for r in current}
    return {
        "added": sorted(cur - previous_symbols),
        "removed": sorted(previous_symbols - cur),
        "kept": sorted(cur & previous_symbols),
    }


def _pack_rows(ranked: list[QuoteRow]) -> list[dict[str, Any]]:
    packed: list[dict[str, Any]] = []
    for r in ranked:
        item = r.to_result_dict()
        if r.total_mv > 0:
            item["total_mv_yi"] = round(r.total_mv / 10_000.0, 2)
        item["score"] = r.__dict__.get("_score")
        item["pattern_score"] = r.__dict__.get("_pattern_score")
        item["pattern_hint"] = r.__dict__.get("_pattern_hint")
        item["hit_reason"] = r.__dict__.get("_hit_reason")
        packed.append(item)
    return packed


def _result(
    *,
    label: str,
    source: str,
    ranked: list[QuoteRow],
    scanned: int,
    req: PatternRunRequest,
    prefs: Any,
    previous_symbols: set[str] | None,
) -> dict[str, Any]:
    return {
        "condition": f"形态 · {label}",
        "source": source,
        "row_count": len(ranked),
        "total_scanned": scanned,
        "config": {
            **req.model_dump(),
            "hard_filter_resolved": prefs.model_dump(),
            "pattern_name": label,
        },
        "rows": _pack_rows(ranked),
        "industry_dist": _industry_dist(ranked),
        "diff": _diff_symbols(ranked, previous_symbols),
    }


def _run_theme_hot(
    req: PatternRunRequest,
    *,
    db: Session,
    pool: list[QuoteRow],
    prefs: Any,
    previous_symbols: set[str] | None,
    suspended_vts: set[str],
) -> dict[str, Any]:
    """涨幅≥2% 且换手≥3%，按 换手×涨幅 打分。"""
    hits: list[tuple[float, QuoteRow]] = []
    scanned = 0
    for row in pool:
        scanned += 1
        if row.change_pct < 2.0 or row.turnover_rate < 3.0:
            continue
        score = round(row.turnover_rate * max(row.change_pct, 0.1), 2)
        hint = "高换手 + 涨幅活跃"
        row.__dict__["_score"] = score
        row.__dict__["_pattern_score"] = score
        row.__dict__["_pattern_hint"] = hint
        row.__dict__["_hit_reason"] = hint
        hits.append((score, row))
    hits.sort(key=lambda pair: pair[0], reverse=True)
    ranked = [r for _, r in hits]
    stock_industry.enrich_rows_from_db(db, ranked)
    ranked = apply_hard_filters(ranked, prefs, suspended_vts=suspended_vts)
    ranked = ranked[: req.top_n]
    label = _PATTERN_LABELS.get("theme_hot", "主题投资")
    return _result(
        label=label,
        source="quote",
        ranked=ranked,
        scanned=scanned,
        req=req,
        prefs=prefs,
        previous_symbols=previous_symbols,
    )


def run_pattern_screen(
    req: PatternRunRequest,
    *,
    db: Session,
    previous_symbols: set[str] | None = None,
    store: QuoteStore | None = None,
) -> dict[str, Any]:
    pid = req.pattern_id.strip()
    if not is_known_pattern(pid):
        raise HTTPException(status_code=400, detail=f"未知形态：{req.pattern_id}")

    quote_store = store or get_quote_store()
    if not quote_store.available():
        raise HTTPException(status_code=503, detail="Redis 不可用，请检查 REDIS_URL 或先启动 Redis")
    meta = quote_store.meta()
    if not meta.get("quote_count"):
        raise HTTPException(
            status_code=503,
            detail="行情快照为空，请启动 quote-collector（python -m app.quote_collector）",
        )

    prefs = resolve_hard_filter(req.hard_filter, req.hard_filter_template)
    suspended_vts = load_suspended_vt_symbols(db)
    pool = quote_store.load_ranked_quotes("change_pct", pool=max(req.max_scan, req.top_n * 5))
    pool = pool[: req.max_scan]

    if pid in QUOTE_ONLY_PATTERNS:
        return _run_theme_hot(
            req,
            db=db,
            pool=pool,
            prefs=prefs,
            previous_symbols=previous_symbols,
            suspended_vts=suspended_vts,
        )

    matcher = get_matcher(pid)
    if matcher is None:
        raise HTTPException(status_code=400, detail=f"未知形态：{req.pattern_id}")

    parse_map: list[tuple[QuoteRow, str, str]] = []
    for row in pool:
        parsed = _parse_tf_symbol(row.symbol)
        if not parsed:
            continue
        parse_map.append((row, parsed[0], parsed[1]))

    series_map = _load_bar_series_batch(
        db,
        [(code, exch) for _, code, exch in parse_map],
        limit=_BAR_LIMIT,
    )

    scanned = 0
    hits: list[tuple[float, QuoteRow]] = []
    for row, code, exch in parse_map:
        series = series_map.get((code, exch))
        if series is None:
            continue
        scanned += 1
        match = matcher(series)
        if match is None:
            continue
        row.__dict__["_score"] = match.score
        row.__dict__["_pattern_score"] = match.score
        row.__dict__["_pattern_hint"] = match.hint
        row.__dict__["_hit_reason"] = match.hint
        if series.closes:
            row.last_price = series.closes[-1]
            if len(series.closes) >= 2 and series.closes[-2] > 0:
                row.change_pct = (series.closes[-1] - series.closes[-2]) / series.closes[-2] * 100
        hits.append((match.score, row))

    hits.sort(key=lambda pair: pair[0], reverse=True)
    ranked = [r for _, r in hits]
    stock_industry.enrich_rows_from_db(db, ranked)
    ranked = apply_hard_filters(ranked, prefs, suspended_vts=suspended_vts)
    ranked = ranked[: req.top_n]

    label = _PATTERN_LABELS.get(pid, pid)
    return _result(
        label=label,
        source="bar",
        ranked=ranked,
        scanned=scanned,
        req=req,
        prefs=prefs,
        previous_symbols=previous_symbols,
    )

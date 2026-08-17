"""选股引擎：条件选股 + 简化多因子 recipe + Tushare 低 PE。"""

from __future__ import annotations

from collections import Counter
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.schemas.screener import ConditionRunRequest, HardFilterPrefs, RecipeRunRequest
from app.services import recipe_weights as recipe_weights_svc
from app.services import stock_industry, tushare_screener
from app.services.hard_filters import apply_hard_filters, resolve_hard_filter
from app.services.presets import get_builtin_recipe, get_preset
from app.services.quotes import QuoteRow, QuoteStore, get_quote_store
from app.services.suspend import load_suspended_vt_symbols


def _industry_dist(rows: list[QuoteRow]) -> list[dict[str, Any]]:
    counter = Counter(r.industry or "未知" for r in rows)
    total = sum(counter.values()) or 1
    return [
        {"industry": name, "count": count, "ratio": round(count / total, 4)} for name, count in counter.most_common()
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


def _require_quotes(store: QuoteStore) -> None:
    if not store.available():
        raise HTTPException(status_code=503, detail="Redis 不可用，请检查 REDIS_URL 或先启动 Redis")
    meta = store.meta()
    if not meta.get("quote_count"):
        raise HTTPException(
            status_code=503,
            detail="行情快照为空，请启动 quote-collector（python -m app.quote_collector）",
        )


def _pack_result(
    rows: list[QuoteRow],
    *,
    total_scanned: int,
    condition: str,
    source: str,
    config: dict[str, Any],
    previous_symbols: set[str] | None,
    hard_filter: HardFilterPrefs,
) -> dict[str, Any]:
    packed_rows: list[dict[str, Any]] = []
    for r in rows:
        item = r.to_result_dict()
        if "_pe_ttm" in r.__dict__:
            item["pe_ttm"] = r.__dict__["_pe_ttm"]
        if "_pb" in r.__dict__:
            item["pb"] = r.__dict__["_pb"]
        if "_net_mf_wan" in r.__dict__:
            item["net_mf_wan"] = r.__dict__["_net_mf_wan"]
        if r.total_mv > 0:
            item["total_mv_yi"] = round(r.total_mv / 10_000.0, 2)
        if "_score" in r.__dict__:
            item["score"] = r.__dict__["_score"]
            item["leader_score"] = r.__dict__["_score"]
        if "_leader_tier" in r.__dict__:
            item["leader_tier"] = r.__dict__["_leader_tier"]
        if "_leader_tier_label" in r.__dict__:
            item["leader_tier_label"] = r.__dict__["_leader_tier_label"]
        if "_hit_reason" in r.__dict__:
            item["hit_reason"] = r.__dict__["_hit_reason"]
        packed_rows.append(item)
    return {
        "condition": condition,
        "source": source,
        "row_count": len(rows),
        "total_scanned": total_scanned,
        "config": {**config, "hard_filter_resolved": hard_filter.model_dump()},
        "rows": packed_rows,
        "industry_dist": _industry_dist(rows),
        "diff": _diff_symbols(rows, previous_symbols),
    }


def _maybe_enrich_industry(db: Session | None, rows: list[QuoteRow]) -> None:
    stock_industry.enrich_rows_from_db(db, rows)


def _enrich_names_from_redis(rows: list[QuoteRow], store: QuoteStore) -> None:
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
        if q.name:
            row.name = q.name
        if q.change_pct:
            row.change_pct = q.change_pct
        if q.last_price:
            row.last_price = q.last_price
        if q.industry:
            row.industry = q.industry
        if q.limit_times:
            row.limit_times = q.limit_times


def run_condition_screen(
    req: ConditionRunRequest,
    *,
    previous_symbols: set[str] | None = None,
    store: QuoteStore | None = None,
    db: Session | None = None,
) -> dict[str, Any]:
    preset = get_preset(req.preset)
    if preset is None:
        raise HTTPException(status_code=400, detail=f"未知 preset：{req.preset}")
    if not preset.implemented:
        raise HTTPException(status_code=501, detail=f"preset「{req.preset}」尚未实现")

    prefs = resolve_hard_filter(req.hard_filter, req.hard_filter_template)
    suspended_vts = load_suspended_vt_symbols(db) if db is not None else set()
    quote_store = store or get_quote_store()

    # —— Tushare 基本面 / 资金流 ——
    if preset.rule_kind == "low_pe":
        rows, trade_date, scanned = tushare_screener.fetch_low_pe_quote_rows(db, max_pe=15.0)
        _enrich_names_from_redis(rows, quote_store)
        _maybe_enrich_industry(db, rows)
        rows = apply_hard_filters(rows, prefs, suspended_vts=suspended_vts)
        rows = rows[: req.top_n]
        return _pack_result(
            rows,
            total_scanned=scanned,
            condition=req.preset,
            source="tushare",
            config={**req.model_dump(), "trade_date": trade_date, "max_pe_ttm": 15.0},
            previous_symbols=previous_symbols,
            hard_filter=prefs,
        )

    if preset.rule_kind == "large_cap":
        rows, trade_date, scanned = tushare_screener.fetch_large_cap_quote_rows(db)
        _enrich_names_from_redis(rows, quote_store)
        _maybe_enrich_industry(db, rows)
        rows = apply_hard_filters(rows, prefs, suspended_vts=suspended_vts)
        rows = rows[: req.top_n]
        return _pack_result(
            rows,
            total_scanned=scanned,
            condition=req.preset,
            source="tushare",
            config={
                **req.model_dump(),
                "trade_date": trade_date,
                "min_total_mv_wan": tushare_screener.MIN_TOTAL_MV_50YI_WAN,
                "min_total_mv_yi": 50.0,
            },
            previous_symbols=previous_symbols,
            hard_filter=prefs,
        )

    if preset.rule_kind == "moneyflow_in":
        # 盘中优先 Redis 资金流排行；无数据再拉 Tushare moneyflow
        redis_rows: list[QuoteRow] = []
        if quote_store.available() and quote_store.meta().get("quote_count"):
            pool = quote_store.load_ranked_quotes("net_mf_amount", pool=max(800, req.top_n * 10))
            redis_rows = [r for r in pool if r.net_mf_amount > 0]
        if redis_rows:
            for r in redis_rows:
                r.__dict__["_net_mf_wan"] = round(r.net_mf_amount, 2)
            _maybe_enrich_industry(db, redis_rows)
            rows = apply_hard_filters(redis_rows, prefs, suspended_vts=suspended_vts)
            rows = rows[: req.top_n]
            return _pack_result(
                rows,
                total_scanned=len(redis_rows),
                condition=req.preset,
                source="quote",
                config={**req.model_dump(), "moneyflow_source": "redis"},
                previous_symbols=previous_symbols,
                hard_filter=prefs,
            )
        rows, trade_date, scanned = tushare_screener.fetch_moneyflow_in_quote_rows(db)
        _enrich_names_from_redis(rows, quote_store)
        _maybe_enrich_industry(db, rows)
        rows = apply_hard_filters(rows, prefs, suspended_vts=suspended_vts)
        rows = rows[: req.top_n]
        return _pack_result(
            rows,
            total_scanned=scanned,
            condition=req.preset,
            source="tushare",
            config={**req.model_dump(), "trade_date": trade_date, "moneyflow_source": "tushare"},
            previous_symbols=previous_symbols,
            hard_filter=prefs,
        )

    # —— 行情类 ——
    _require_quotes(quote_store)

    if preset.rule_kind == "limit_up":
        pool = quote_store.load_ranked_quotes("limit_times", pool=max(800, req.top_n * 10))
        if not pool:
            pool = quote_store.load_ranked_quotes("change_pct", pool=max(800, req.top_n * 10))
        total_scanned = len(pool)
        rows = [r for r in pool if r.limit_times >= 1 or r.change_pct >= 9.5]
        rows.sort(key=lambda r: (r.limit_times, r.change_pct), reverse=True)
    else:
        rank_field = {
            "change_top": "change_pct",
            "strong_up": "change_pct",
            "turnover": "turnover_rate",
            "volume_ratio": "volume_ratio",
            "volume": "volume",
            "custom": "change_pct",
        }[preset.rule_kind]
        pool = quote_store.load_ranked_quotes(rank_field, pool=max(500, req.top_n * 5))
        total_scanned = len(pool)
        rows = list(pool)
        if preset.rule_kind == "strong_up":
            rows = [r for r in rows if r.change_pct >= 5.0]
        elif preset.rule_kind == "custom":
            if req.min_change_pct is not None:
                rows = [r for r in rows if r.change_pct >= req.min_change_pct]
            if req.max_change_pct is not None:
                rows = [r for r in rows if r.change_pct <= req.max_change_pct]
            if req.min_turnover_rate is not None:
                rows = [r for r in rows if r.turnover_rate >= req.min_turnover_rate]
            if req.max_turnover_rate is not None:
                rows = [r for r in rows if r.turnover_rate <= req.max_turnover_rate]

    _maybe_enrich_industry(db, rows)
    rows = apply_hard_filters(rows, prefs, suspended_vts=suspended_vts)
    rows = rows[: req.top_n]
    return _pack_result(
        rows,
        total_scanned=total_scanned,
        condition=req.preset,
        source="quote",
        config=req.model_dump(),
        previous_symbols=previous_symbols,
        hard_filter=prefs,
    )


def _score_intraday_multi(row: QuoteRow, weights: dict[str, float] | None = None) -> float:
    w = weights or recipe_weights_svc.DEFAULT_WEIGHTS["intraday_multi"]
    momentum = max(0.0, min(row.change_pct / 10.0, 1.0))
    turnover = max(0.0, min(row.turnover_rate / 15.0, 1.0))
    vr = max(0.0, min(row.volume_ratio / 5.0, 1.0))
    surge = max(0.0, min(row.amount / 5e8, 1.0))
    return (
        w.get("momentum", 0.35) * momentum
        + w.get("turnover", 0.25) * turnover
        + w.get("volume_ratio", 0.25) * vr
        + w.get("surge", 0.15) * surge
    )


def _score_ultra_short(row: QuoteRow, weights: dict[str, float] | None = None) -> float:
    w = weights or recipe_weights_svc.DEFAULT_WEIGHTS["ultra_short_unified"]
    board = max(0.0, min(row.limit_times / 3.0, 1.0))
    momentum = max(0.0, min(row.change_pct / 10.0, 1.0))
    turnover = max(0.0, min(row.turnover_rate / 20.0, 1.0))
    return w.get("board", 0.4) * board + w.get("momentum", 0.35) * momentum + w.get("turnover", 0.25) * turnover


def _score_post_close_multi(row: QuoteRow, weights: dict[str, float] | None = None) -> float:
    """资金 + 动量 + 换手 + 弱估值（对齐桌面 post_close_multi 方向，简化版）。"""
    w = weights or recipe_weights_svc.DEFAULT_WEIGHTS["post_close_multi"]
    mf = max(0.0, min(row.net_mf_amount / 5_000.0, 1.0))
    momentum = max(0.0, min(max(row.change_pct, 0.0) / 8.0, 1.0))
    turnover = max(0.0, min(row.turnover_rate / 12.0, 1.0))
    pe = float(row.__dict__.get("_pe_ttm") or 0)
    if pe > 0:
        valuation = max(0.0, min((40.0 - pe) / 40.0, 1.0))
    else:
        mv = row.total_mv or row.circ_mv
        valuation = max(0.0, min(mv / 1_000_000.0, 1.0)) * 0.5
    return (
        w.get("moneyflow", 0.4) * mf
        + w.get("momentum", 0.3) * momentum
        + w.get("turnover", 0.2) * turnover
        + w.get("valuation", 0.1) * valuation
    )


_RECIPE_SCORERS = {
    "intraday_multi": _score_intraday_multi,
    "ultra_short_unified": _score_ultra_short,
    "post_close_multi": _score_post_close_multi,
}


def run_recipe_screen(
    req: RecipeRunRequest,
    *,
    previous_symbols: set[str] | None = None,
    store: QuoteStore | None = None,
    db: Session | None = None,
    user_id: str | None = None,
) -> dict[str, Any]:
    recipe = get_builtin_recipe(req.recipe_id)
    if recipe is None:
        raise HTTPException(status_code=400, detail=f"未知 recipe：{req.recipe_id}")
    if not recipe.implemented:
        raise HTTPException(status_code=501, detail=f"recipe「{req.recipe_id}」尚未实现")

    prefs = resolve_hard_filter(req.hard_filter, req.hard_filter_template)
    suspended_vts = load_suspended_vt_symbols(db) if db is not None else set()
    top_n = req.top_n or recipe.top_n

    if recipe.recipe_id == "radar_leader":
        from app.services import leader_screen

        variant = req.variant if req.variant in ("mainline", "all_market") else "mainline"
        return leader_screen.run_leader_screen(
            top_n=top_n,
            variant=variant,  # type: ignore[arg-type]
            hard_filter=prefs,
            previous_symbols=previous_symbols,
            store=store,
            db=db,
        )

    if recipe.recipe_id == "radar_resonance":
        from app.services import resonance_screen

        if db is None or not user_id:
            raise HTTPException(status_code=400, detail="雷达共振需要数据库与登录用户")
        return resonance_screen.run_resonance_screen(
            db=db,
            user_id=user_id,
            top_n=top_n,
            hard_filter=prefs,
            previous_symbols=previous_symbols,
        )

    quote_store = store or get_quote_store()
    _require_quotes(quote_store)

    if recipe.recipe_id == "post_close_multi":
        mf_pool = quote_store.load_ranked_quotes("net_mf_amount", pool=400)
        if any(r.net_mf_amount > 0 for r in mf_pool):
            pool = mf_pool
        else:
            pool = quote_store.load_ranked_quotes("change_pct", pool=400)
    else:
        pool = quote_store.load_ranked_quotes("change_pct", pool=400)
    total_scanned = len(pool)
    _maybe_enrich_industry(db, pool)
    rows = apply_hard_filters(pool, prefs, suspended_vts=suspended_vts)

    weights: dict[str, float] | None = None
    if recipe.recipe_id in recipe_weights_svc.EDITABLE_RECIPES and db is not None and user_id:
        try:
            weights = recipe_weights_svc.load_recipe_weights(db, user_id, recipe.recipe_id)
        except ValueError:
            weights = None

    scorer = _RECIPE_SCORERS.get(recipe.recipe_id, _score_intraday_multi)
    if recipe.recipe_id in recipe_weights_svc.EDITABLE_RECIPES:
        scored = [(scorer(r, weights), r) for r in rows]  # type: ignore[call-arg]
    else:
        scored = [(scorer(r), r) for r in rows]
    scored.sort(key=lambda x: x[0], reverse=True)
    selected = [r for _, r in scored[:top_n]]
    for score, row in scored[:top_n]:
        row.__dict__["_score"] = round(score, 4)  # type: ignore[attr-defined]

    return _pack_result(
        selected,
        total_scanned=total_scanned,
        condition=recipe.name,
        source="recipe",
        config=req.model_dump(),
        previous_symbols=previous_symbols,
        hard_filter=prefs,
    )

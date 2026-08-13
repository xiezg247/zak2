"""雷达龙头选股（简化 leader_score，不依赖 vnpy）。"""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any, Literal

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.schemas.screener import HardFilterPrefs
from app.services.hard_filters import apply_hard_filters
from app.services import stock_industry
from app.services.suspend import load_suspended_vt_symbols
from app.services.limit_list_store import load_first_time_map
from app.services.quotes import QuoteRow, QuoteStore, get_quote_store
from app.services.seal_time import format_seal_time_label, seal_time_score
from app.services import emotion_cycle as emotion_cycle_svc
from app.services import market as market_svc

LeaderVariant = Literal["mainline", "all_market"]

_WEIGHTS: dict[str, float] = {
    "limit_times": 0.28,
    "seal_quality": 0.16,
    "amount_rank": 0.16,
    "seal_time": 0.12,
    "net_mf": 0.15,
    "sector_strength": 0.13,
}

_STAGE_LABELS = emotion_cycle_svc.STAGE_LABELS

_VARIANT_LABELS = {
    "mainline": "主线龙头",
    "all_market": "全市场龙头",
}

FOLLOWER_MIN_SCORE = 35.0


def resolve_emotion_stage(db: Session | None) -> tuple[str | None, dict[str, Any] | None]:
    """优先完整情绪周期；无数据时回退梯队高度近似。"""
    if db is None:
        return None, None
    cycle = emotion_cycle_svc.build_emotion_cycle(db)
    stage = str(cycle.get("stage") or "") or None
    if cycle.get("source") and cycle.get("source") != "empty":
        return stage, cycle
    emotion = market_svc.load_emotion(db)
    if not emotion:
        return stage, cycle
    # 仅有空 inputs 时再用高度粗推
    inputs = cycle.get("inputs") or {}
    if int(inputs.get("sample_size") or 0) == 0 and int(inputs.get("max_limit_times") or 0) == 0:
        mx = int(emotion.get("max_limit_times") or 0)
        if mx <= 0:
            return "ice", cycle
        if mx == 1:
            return "startup", cycle
        if mx >= 5:
            return "climax", cycle
        if mx >= 3:
            return "divergence", cycle
        return "startup", cycle
    return stage, cycle


# 兼容旧测试名
def infer_emotion_stage(emotion: dict[str, Any] | None) -> str | None:
    """用连板高度粗推（仅单测/fallback）。"""
    if not emotion:
        return None
    mx = int(emotion.get("max_limit_times") or 0)
    if mx <= 0:
        return "ice"
    if mx == 1:
        return "startup"
    if mx >= 5:
        return "climax"
    if mx >= 3:
        return "divergence"
    return "startup"


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def _norm_limit_times(limit_times: float) -> float:
    boards = max(0.0, limit_times)
    if boards <= 0:
        return 0.2
    return _clamp01(boards / 5.0)


def _seal_quality(row: QuoteRow) -> float:
    if row.limit_times < 1 and row.change_pct < 9.5:
        return _clamp01(row.change_pct / 10.0 * 0.6)
    if row.amplitude > 0 and row.amplitude < 0.5:
        return 0.25
    amount = row.amount
    if amount >= 5e8:
        return 1.0
    if amount >= 1e8:
        return 0.75
    if amount >= 5e7:
        return 0.55
    return 0.4


def _norm_net_mf(row: QuoteRow, *, max_abs: float) -> float:
    raw = row.net_mf_amount
    if max_abs <= 0:
        return 0.5 if raw > 0 else 0.0
    if raw <= 0:
        return 0.0
    return _clamp01(raw / max_abs)


def _amount_ranks(rows: list[QuoteRow]) -> dict[str, float]:
    amounts = sorted(r.amount for r in rows)
    n = len(amounts) or 1
    out: dict[str, float] = {}
    for row in rows:
        if row.amount <= 0:
            out[row.symbol] = 0.0
            continue
        rank = sum(1 for a in amounts if a <= row.amount)
        out[row.symbol] = _clamp01(rank / n)
    return out


def _sector_strength_map(rows: list[QuoteRow]) -> dict[str, float]:
    counter = Counter((r.industry or "未知").strip() or "未知" for r in rows)
    max_c = max(counter.values()) if counter else 1
    return {name: _clamp01(count / max_c) for name, count in counter.items()}


def compute_leader_score(
    row: QuoteRow,
    *,
    amount_rank: float,
    sector_strength: float,
    max_net_mf: float,
    seal_time: float = 0.0,
) -> float:
    parts = {
        "limit_times": _norm_limit_times(float(row.limit_times)),
        "seal_quality": _seal_quality(row),
        "amount_rank": _clamp01(amount_rank),
        "seal_time": _clamp01(seal_time),
        "net_mf": _norm_net_mf(row, max_abs=max_net_mf),
        "sector_strength": _clamp01(sector_strength),
    }
    score = 100.0 * sum(_WEIGHTS[k] * parts[k] for k in _WEIGHTS)
    return round(score, 2)


def _tier_for_index(index: int, score: float) -> str:
    if index == 0:
        return "dragon_1"
    if index == 1:
        return "dragon_2"
    if index < 5 and score >= FOLLOWER_MIN_SCORE:
        return "follower"
    return ""


def _tier_label(tier: str) -> str:
    return {"dragon_1": "龙一", "dragon_2": "龙二", "follower": "跟风"}.get(tier, "")


def build_candidate_pool(store: QuoteStore, *, pool_size: int = 120) -> tuple[list[QuoteRow], int]:
    pool = store.load_ranked_quotes("limit_times", pool=max(pool_size, 80))
    if len(pool) < 20:
        pool = store.load_ranked_quotes("change_pct", pool=max(pool_size, 200))
    total = len(pool)
    candidates = [r for r in pool if r.limit_times >= 1 or r.change_pct >= 9.5]
    if not candidates:
        candidates = list(pool[:pool_size])
    return candidates[:pool_size], total


def rank_leader_pool(
    rows: list[QuoteRow],
    *,
    top_n: int,
    variant: LeaderVariant = "mainline",
    filter_followers: bool = False,
    first_time_map: dict[str, str] | None = None,
) -> list[QuoteRow]:
    if not rows:
        return []

    ft_map = first_time_map or {}
    amount_rank = _amount_ranks(rows)
    sector_strength = _sector_strength_map(rows)
    max_mf = max((abs(r.net_mf_amount) for r in rows), default=0.0)

    scored: list[tuple[float, QuoteRow, str]] = []
    for row in rows:
        industry = (row.industry or "未知").strip() or "未知"
        first_time = str(ft_map.get(row.symbol) or "").strip()
        st_score = seal_time_score(first_time)
        st_label = format_seal_time_label(first_time)
        row.__dict__["_first_time"] = first_time
        row.__dict__["_seal_time_score"] = st_score
        row.__dict__["_seal_time_label"] = st_label
        score = compute_leader_score(
            row,
            amount_rank=amount_rank.get(row.symbol, 0.5),
            sector_strength=sector_strength.get(industry, 0.0),
            max_net_mf=max_mf,
            seal_time=st_score,
        )
        scored.append((score, row, industry))

    by_industry: dict[str, list[tuple[float, QuoteRow]]] = defaultdict(list)
    for score, row, industry in scored:
        by_industry[industry].append((score, row))
    for industry in by_industry:
        by_industry[industry].sort(key=lambda x: x[0], reverse=True)

    strong = {name for name, items in by_industry.items() if len(items) >= 2 and name != "未知"}
    if variant == "mainline" and strong:
        industry_order = sorted(strong, key=lambda n: max(s for s, _ in by_industry[n]), reverse=True)
    else:
        industry_order = sorted(
            by_industry.keys(),
            key=lambda n: max((s for s, _ in by_industry[n]), default=0.0),
            reverse=True,
        )

    selected: list[QuoteRow] = []
    for industry in industry_order:
        group = by_industry[industry]
        for index, (score, row) in enumerate(group):
            tier = _tier_for_index(index, score)
            if not tier:
                continue
            if filter_followers and tier == "follower":
                continue
            if variant == "mainline" and strong and industry not in strong and tier == "follower":
                continue
            row.__dict__["_score"] = score
            row.__dict__["_leader_tier"] = tier
            row.__dict__["_leader_tier_label"] = _tier_label(tier)
            hit = (
                f"龙头 {_tier_label(tier)} · {industry} · 评分 {score:.0f} · "
                f"连板 {int(row.limit_times) if row.limit_times >= 1 else '—'}"
            )
            seal_label = str(row.__dict__.get("_seal_time_label") or "")
            if seal_label:
                hit += f" · {seal_label}"
            row.__dict__["_hit_reason"] = hit
            if not row.industry:
                row.industry = industry
            selected.append(row)
            if len(selected) >= top_n:
                return selected
    return selected[:top_n]


def _write_seal_time_fields(rows: list[dict[str, Any]], first_time_map: dict[str, str]) -> None:
    """结果行写出 first_time / seal_time_*。

    打包后的 vt_symbol 是桌面键（如 600519.SSE），与 first_time_map 的 TickFlow 键
    （SHSE.600519）不一致；此处只用 symbol / tf_symbol 查表，忽略 vt_symbol。
    """
    for item in rows:
        if not item.get("tf_symbol") and item.get("symbol"):
            item["tf_symbol"] = str(item["symbol"])
        key = str(item.get("tf_symbol") or item.get("symbol") or "").strip()
        first_time = str(first_time_map.get(key) or "").strip()
        item["first_time"] = first_time
        item["seal_time_score"] = seal_time_score(first_time)
        item["seal_time_label"] = format_seal_time_label(first_time)


def run_leader_screen(
    *,
    top_n: int = 12,
    variant: LeaderVariant = "mainline",
    hard_filter: HardFilterPrefs,
    previous_symbols: set[str] | None = None,
    store: QuoteStore | None = None,
    db: Session | None = None,
) -> dict[str, Any]:
    from app.services.engine import _diff_symbols, _industry_dist, _pack_result, _require_quotes

    quote_store = store or get_quote_store()
    _require_quotes(quote_store)

    stage, cycle = resolve_emotion_stage(db)
    emotion = market_svc.load_emotion(db) if db is not None else None
    variant_label = _VARIANT_LABELS.get(variant, variant)
    stage_label = _STAGE_LABELS.get(stage or "", "") or (cycle or {}).get("stage_label", "")

    if stage in {"ice", "recession"}:
        condition = f"雷达龙头（{stage_label or stage}·不宜新开）"
        return _pack_result(
            [],
            total_scanned=0,
            condition=condition,
            source="radar_leader",
            config={
                "recipe_id": "radar_leader",
                "variant": variant,
                "emotion_stage": stage,
                "emotion_cycle": cycle,
                "top_n": top_n,
                "hard_filter_resolved": hard_filter.model_dump(),
            },
            previous_symbols=previous_symbols,
            hard_filter=hard_filter,
        )

    candidates, total_scanned = build_candidate_pool(quote_store, pool_size=max(top_n * 8, 80))
    stock_industry.enrich_rows_from_db(db, candidates)
    suspended_vts = load_suspended_vt_symbols(db) if db is not None else set()
    filtered = apply_hard_filters(candidates, hard_filter, suspended_vts=suspended_vts)
    if not filtered:
        raise HTTPException(status_code=400, detail="硬过滤后无龙头候选，可调低过滤条件或刷新行情")

    first_time_map = load_first_time_map(db) if db is not None else {}
    filter_followers = stage == "divergence"
    ranked = rank_leader_pool(
        filtered,
        top_n=top_n,
        variant=variant,
        filter_followers=filter_followers,
        first_time_map=first_time_map,
    )

    condition = f"雷达龙头 · {variant_label}"
    if stage_label:
        condition += f" · {stage_label}"

    result = _pack_result(
        ranked,
        total_scanned=total_scanned,
        condition=condition,
        source="radar_leader",
        config={
            "recipe_id": "radar_leader",
            "variant": variant,
            "emotion_stage": stage,
            "emotion_cycle": cycle,
            "top_n": top_n,
            "hard_filter_resolved": hard_filter.model_dump(),
            "filter_followers": filter_followers,
        },
        previous_symbols=previous_symbols,
        hard_filter=hard_filter,
    )
    _write_seal_time_fields(result.get("rows") or [], first_time_map)
    # 附带行业分布（已在 pack）；补充情绪摘要
    result["emotion"] = emotion
    result["emotion_cycle"] = cycle
    result["industry_dist"] = _industry_dist(ranked) or result.get("industry_dist") or []
    result["diff"] = _diff_symbols(ranked, previous_symbols)
    return result


def synth_leader_pick_rows(
    db: Session,
    *,
    top_n: int = 12,
    variant: LeaderVariant = "mainline",
) -> tuple[list[dict[str, Any]], str, str]:
    """供雷达卡片合成：返回 (rows, subtitle, empty_message)。"""
    store = get_quote_store()
    if not store.available() or not store.meta().get("quote_count"):
        return [], "", "行情快照为空，请启动 quote-collector"

    stage, cycle = resolve_emotion_stage(db)
    stage_label = _STAGE_LABELS.get(stage or "", "") or str((cycle or {}).get("stage_label") or "")
    if stage in {"ice", "recession"}:
        return [], stage_label, f"{stage_label or '退潮'}环境不宜新开龙头"

    prefs = HardFilterPrefs(min_amount_wan=0, min_total_mv_yi=0, exclude_st=True)
    candidates, _ = build_candidate_pool(store, pool_size=100)
    stock_industry.enrich_rows_from_db(db, candidates)
    suspended_vts = load_suspended_vt_symbols(db)
    filtered = apply_hard_filters(candidates, prefs, suspended_vts=suspended_vts)
    first_time_map = load_first_time_map(db)
    ranked = rank_leader_pool(
        filtered,
        top_n=top_n,
        variant=variant,
        filter_followers=stage == "divergence",
        first_time_map=first_time_map,
    )
    rows = []
    for r in ranked:
        rows.append(
            {
                "tf_symbol": r.symbol,
                "name": r.name,
                "change_pct": r.change_pct,
                "limit_times": r.limit_times,
                "leader_score": r.__dict__.get("_score"),
                "leader_tier": r.__dict__.get("_leader_tier_label") or r.__dict__.get("_leader_tier"),
                "industry": r.industry,
                "first_time": r.__dict__.get("_first_time", ""),
                "seal_time_score": r.__dict__.get("_seal_time_score", 0.0),
                "seal_time_label": r.__dict__.get("_seal_time_label", ""),
            }
        )
    subtitle = " · ".join(x for x in (_VARIANT_LABELS[variant], stage_label) if x)
    return rows, subtitle, "" if rows else "暂无龙头候选"

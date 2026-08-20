"""情绪周期：五阶段判定（迟滞 + 大盘 MA5 + 恐贪代理）。"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.market import EmotionLimitLadderDaily
from app.domains.market.schemas import EmotionCycleOut
from app.domains.emotion import emotion_cycle_cache, emotion_hysteresis
from app.domains.market.quotes import get_quote_store

LIMIT_UP_PCT = 9.85
LIMIT_DOWN_PCT = -9.85

STAGE_LABELS = {
    "ice": "冰点",
    "startup": "启动",
    "climax": "发酵/高潮",
    "divergence": "分歧",
    "recession": "退潮",
}

_STAGE_POSITION = {
    "ice": (0.0, 0.10),
    "startup": (0.30, 0.50),
    "climax": (0.60, 0.80),
    "divergence": (0.0, 0.30),
    "recession": (0.0, 0.0),
}

_STAGE_MODES = {
    "ice": (),
    "startup": ("limit_board", "halfway"),
    "climax": ("limit_board", "halfway"),
    "divergence": ("pullback",),
    "recession": (),
}

_MODE_LABELS = {
    "limit_board": "打板",
    "halfway": "半路",
    "pullback": "低吸",
}


@dataclass(frozen=True)
class Thresholds:
    recession_limit_down: int = 20
    ice_max_boards: int = 2
    ice_limit_down: int = 15
    ice_up_ratio_max: float = 0.35
    climax_ladder_depth: int = 3
    climax_limit_up: int = 80
    divergence_limit_up_min: int = 30
    divergence_limit_spread: int = 10
    startup_max_boards: int = 3
    startup_limit_up: int = 50
    amount_floor_yuan: float = 1e12
    recession_break_rate: float = 0.5
    fear_greed_overheat: float = 85.0
    hysteresis_enabled: bool = True


DEFAULT_THRESHOLDS = Thresholds()


def classify_stage(
    *,
    limit_up_count: int,
    limit_down_count: int,
    up_ratio: float,
    max_limit_times: int,
    limit_ladder_depth: int,
    prev_leader_limit_down: bool = False,
    limit_break_rate: float | None = None,
    thresholds: Thresholds = DEFAULT_THRESHOLDS,
) -> str:
    """判定顺序：退潮 → 冰点 → 高潮 → 分歧 → 启动 → 默认分歧。"""
    t = thresholds
    if limit_down_count >= t.recession_limit_down:
        return "recession"
    if prev_leader_limit_down:
        return "recession"
    if limit_break_rate is not None and limit_break_rate >= t.recession_break_rate:
        return "recession"
    if max_limit_times <= t.ice_max_boards and limit_down_count >= t.ice_limit_down and up_ratio < t.ice_up_ratio_max:
        return "ice"
    if limit_ladder_depth >= t.climax_ladder_depth and limit_up_count >= t.climax_limit_up:
        return "climax"
    if (
        limit_up_count >= t.divergence_limit_up_min
        and abs(limit_up_count - limit_down_count) <= t.divergence_limit_spread
    ):
        return "divergence"
    if max_limit_times >= t.startup_max_boards or limit_up_count >= t.startup_limit_up:
        return "startup"
    return "divergence"


def estimate_fear_greed_proxy(*, up_ratio: float, limit_up_count: int, limit_down_count: int) -> float:
    """广度简化恐贪代理 0–100（非桌面 SentimentService 全量）。"""
    ud = max(0, limit_up_count) + max(0, limit_down_count)
    limit_balance = (limit_up_count / ud) if ud > 0 else 0.5
    score = max(0.0, min(1.0, up_ratio)) * 55.0 + min(max(limit_up_count, 0) / 100.0, 1.0) * 30.0
    score += limit_balance * 15.0
    return round(max(0.0, min(100.0, score)), 1)


def _ladder_rows(db: Session, *, limit: int = 2) -> list[EmotionLimitLadderDaily]:
    return list(
        db.scalars(select(EmotionLimitLadderDaily).order_by(EmotionLimitLadderDaily.trade_date.desc()).limit(limit))
    )


def _parse_linked(raw: str | None) -> list[str]:
    try:
        parsed = json.loads(raw or "[]")
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    return [str(x) for x in parsed]


def _index_above_ma5(db: Session) -> bool | None:
    """上证综指收盘相对 5 日均线；无本地日 K 则返回 None。"""
    try:
        from app.domains.market.bars import load_bars

        resp = load_bars(db, symbol="000001", exchange="SSE", interval="d", limit=8)
    except Exception:
        return None
    bars = sorted(resp.bars or [], key=lambda b: b.datetime)
    if len(bars) < 5:
        return None
    closes = [float(b.close) for b in bars[-5:]]
    ma5 = sum(closes) / 5.0
    return closes[-1] >= ma5


def _breadth_from_redis(*, pool: int = 4000) -> dict[str, Any] | None:
    store = get_quote_store()
    if not store.available() or not store.meta().get("quote_count"):
        return None
    ranked = store.list_rank("change_pct", top_n=pool)
    if not ranked:
        return None
    quotes = store.get_quotes([sym for sym, _ in ranked])
    if not quotes:
        limit_up = sum(1 for _, score in ranked if score >= LIMIT_UP_PCT)
        limit_down = sum(1 for _, score in ranked if score <= LIMIT_DOWN_PCT)
        up = sum(1 for _, score in ranked if score > 0)
        down = sum(1 for _, score in ranked if score < 0)
        total_ud = up + down
        return {
            "limit_up_count": limit_up,
            "limit_down_count": limit_down,
            "up_ratio": (up / total_ud) if total_ud else 0.5,
            "total_amount": 0.0,
            "sample_size": len(ranked),
            "max_limit_times": 0,
            "limit_ladder_depth": 0,
        }

    limit_up = 0
    limit_down = 0
    up = 0
    down = 0
    total_amount = 0.0
    board_levels: set[int] = set()
    max_boards = 0
    for q in quotes:
        cp = q.change_pct
        total_amount += max(0.0, q.amount)
        if cp > 0:
            up += 1
        elif cp < 0:
            down += 1
        if cp >= LIMIT_UP_PCT or q.limit_times >= 1:
            limit_up += 1
        if cp <= LIMIT_DOWN_PCT:
            limit_down += 1
        boards = int(q.limit_times or 0)
        if boards >= 1:
            max_boards = max(max_boards, boards)
        if boards >= 2:
            board_levels.add(boards)
    total_ud = up + down
    return {
        "limit_up_count": limit_up,
        "limit_down_count": limit_down,
        "up_ratio": (up / total_ud) if total_ud else 0.5,
        "total_amount": total_amount,
        "sample_size": len(quotes),
        "max_limit_times": max_boards,
        "limit_ladder_depth": len(board_levels),
    }


def _prev_leader_limit_down(db: Session, today_quotes_by_vt: dict[str, float]) -> bool:
    rows = _ladder_rows(db, limit=2)
    if len(rows) < 1:
        return False
    prev = rows[1] if len(rows) >= 2 else None
    if prev is None:
        return False
    leader = str(prev.max_board_vt_symbol or "").strip()
    if not leader:
        return False
    change = today_quotes_by_vt.get(leader)
    if change is None and "." in leader:
        code, _exch = leader.rsplit(".", 1)
        for vt, cp in today_quotes_by_vt.items():
            if vt.endswith(f".{code}") or vt.startswith(f"{code}."):
                change = cp
                break
    return change is not None and change <= LIMIT_DOWN_PCT


def _approx_break_rate(db: Session, today_max: int) -> float | None:
    """昨最高板 vs 今最高板的简易断板近似。"""
    rows = _ladder_rows(db, limit=2)
    if len(rows) < 2:
        return None
    prev_max = int(rows[1].max_limit_times or 0)
    if prev_max <= 0:
        return None
    drop = max(0, prev_max - max(0, today_max))
    return min(1.0, drop / prev_max)


def build_emotion_cycle(db: Session, *, force: bool = False) -> EmotionCycleOut:
    """组装 inputs → classify → hysteresis → 辅助因子调整。"""
    if not force:
        hit = emotion_cycle_cache.cache_get()
        if hit is not None:
            return hit

    breadth = _breadth_from_redis()
    ladder = _ladder_rows(db, limit=2)
    today_ladder = ladder[0] if ladder else None

    limit_up = int((breadth or {}).get("limit_up_count") or 0)
    limit_down = int((breadth or {}).get("limit_down_count") or 0)
    up_ratio = float((breadth or {}).get("up_ratio") or 0.5)
    total_amount = float((breadth or {}).get("total_amount") or 0)
    max_boards = int((breadth or {}).get("max_limit_times") or 0)
    ladder_depth = int((breadth or {}).get("limit_ladder_depth") or 0)
    source_parts: list[str] = []

    if breadth:
        source_parts.append("redis")
    if today_ladder:
        source_parts.append("ladder")
        mx = int(today_ladder.max_limit_times or 0)
        max_boards = max(max_boards, mx)
        if mx >= 2:
            ladder_depth = max(ladder_depth, mx - 1 if mx >= 3 else 1)

    today_change: dict[str, float] = {}
    if breadth and get_quote_store().available():
        ranked = get_quote_store().list_rank("change_pct", top_n=800)
        quotes = get_quote_store().get_quotes([s for s, _ in ranked[:200]])
        from app.services.symbols import normalize_exchange, to_vt_symbol

        for q in quotes:
            parts = q.symbol.split(".", 1)
            if len(parts) == 2:
                vt = to_vt_symbol(parts[1], normalize_exchange(parts[0]))
                today_change[vt] = q.change_pct
                today_change[q.symbol] = q.change_pct
    prev_leader_ld = _prev_leader_limit_down(db, today_change)
    break_rate = _approx_break_rate(db, max_boards)

    index_above = _index_above_ma5(db)
    if index_above is not None:
        source_parts.append("ma5")
    fear_greed = estimate_fear_greed_proxy(
        up_ratio=up_ratio,
        limit_up_count=limit_up,
        limit_down_count=limit_down,
    )
    source_parts.append("fg_proxy")

    from app.domains.emotion.emotion_thresholds import load_thresholds

    thresholds, _ = load_thresholds(db)
    t = thresholds
    if not breadth and today_ladder:
        mx = int(today_ladder.max_limit_times or 0)
        if mx <= 0:
            raw_stage = "ice"
        elif mx == 1:
            raw_stage = "startup"
        elif mx >= 5:
            raw_stage = "climax"
        elif mx >= 3:
            raw_stage = "divergence"
        else:
            raw_stage = "startup"
        source_parts = ["ladder_fallback", "fg_proxy"]
        if index_above is not None:
            source_parts.append("ma5")
    else:
        raw_stage = classify_stage(
            limit_up_count=limit_up,
            limit_down_count=limit_down,
            up_ratio=up_ratio,
            max_limit_times=max_boards,
            limit_ladder_depth=ladder_depth,
            prev_leader_limit_down=prev_leader_ld,
            limit_break_rate=break_rate,
            thresholds=t,
        )

    inputs_for_hyst = {
        "limit_up_count": limit_up,
        "max_limit_times": max_boards,
        "limit_ladder_depth": ladder_depth,
    }
    stage = emotion_hysteresis.apply_stage_hysteresis(
        raw_stage,
        inputs_for_hyst,
        t,
        enabled=t.hysteresis_enabled,
    )

    pct_min, pct_max = _STAGE_POSITION[stage]
    factor = (pct_min + pct_max) / 2.0 if pct_max > 0 else 0.0
    warnings: list[str] = []
    modes = list(_STAGE_MODES[stage])

    if total_amount > 0 and total_amount < t.amount_floor_yuan:
        factor *= 0.7
        warnings.append("成交额不足 1 万亿，建议降仓")
    if index_above is False:
        factor *= 0.8
        modes = [m for m in modes if m != "limit_board"]
        warnings.append("大盘 5 日线向下，回避打板")
    if break_rate is not None and break_rate >= t.recession_break_rate:
        warnings.append(f"连板断板率约 {break_rate * 100:.0f}%，高度板分歧")
    if prev_leader_ld:
        warnings.append("昨最高连板今日跌停，退潮信号")
    if fear_greed > t.fear_greed_overheat:
        warnings.append(f"恐贪代理 {fear_greed:.0f} 偏高，注意过热")

    allow_new = stage not in {"ice", "recession"}
    factor = min(1.0, max(0.0, factor))
    out = {
        "stage": stage,
        "raw_stage": raw_stage,
        "stage_label": STAGE_LABELS.get(stage, stage),
        "position_factor": round(factor, 4),
        "position_pct_min": pct_min,
        "position_pct_max": pct_max,
        "allow_new_positions": allow_new,
        "allowed_modes": modes,
        "allowed_mode_labels": [_MODE_LABELS.get(m, m) for m in modes],
        "warnings": warnings,
        "source": "+".join(source_parts) if source_parts else "empty",
        "trade_date": today_ladder.trade_date if today_ladder else None,
        "inputs": {
            "limit_up_count": limit_up,
            "limit_down_count": limit_down,
            "up_ratio": round(up_ratio, 4),
            "total_amount": total_amount,
            "max_limit_times": max_boards,
            "limit_ladder_depth": ladder_depth,
            "prev_leader_limit_down": prev_leader_ld,
            "limit_break_rate": round(break_rate, 4) if break_rate is not None else None,
            "index_above_ma5": index_above,
            "fear_greed_index": fear_greed,
            "fear_greed_source": "breadth_proxy",
            "sample_size": int((breadth or {}).get("sample_size") or 0),
        },
    }
    result = EmotionCycleOut(**out)
    emotion_cycle_cache.cache_set(result)
    return result

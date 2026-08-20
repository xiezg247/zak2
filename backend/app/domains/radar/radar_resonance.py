"""雷达跨卡共振汇总（可调权重 + 出现次数）。"""

from __future__ import annotations

import json
import math
from contextlib import suppress
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.domains.market.schemas import (
    RadarCardOut,
    RadarResonanceEntry,
    RadarResonanceOut,
    RadarResonanceWeightItem,
    RadarResonanceWeightsOut,
)
from app.domains.market.limit_list_store import lookup_first_time
from app.domains.market.quotes import _to_vt_symbol
from app.domains.market.seal_time import format_seal_time_label
from app.domains.radar.cards import list_radar_cards
from app.services.symbols import parse_flexible_symbol, to_vt_symbol

# 默认权重（对齐桌面「短线」略偏龙头/连板）；用户可通过 meta 覆盖可编辑项
CARD_WEIGHTS: dict[str, float] = {
    "leader_pick": 1.5,
    "discovery_limit_ladder": 1.4,
    "discovery_limit_break": 1.3,
    "discovery_change_top": 1.0,
    "discovery_volume_surge": 1.0,
    "discovery_moneyflow_intraday": 1.1,
    "watchlist_short_term": 1.0,
    "watchlist_intraday": 1.0,
    "sector_flow_hot": 0.0,  # 板块行无个股 vt
    "sector_theme": 0.0,
}

CARD_TITLES: dict[str, str] = {
    "leader_pick": "选股·龙头",
    "discovery_limit_ladder": "发现·连板梯队",
    "discovery_limit_break": "发现·炸板断板",
    "discovery_change_top": "发现·涨幅前列",
    "discovery_volume_surge": "发现·放量异动",
    "discovery_moneyflow_intraday": "发现·资金异动",
    "watchlist_short_term": "自选·短线关注",
    "watchlist_intraday": "自选·异动",
    "sector_flow_hot": "板块·资金热度",
    "sector_theme": "板块·主线",
}


def editable_card_ids() -> list[str]:
    return [card_id for card_id, weight in CARD_WEIGHTS.items() if weight > 0]


def merge_weights(stored: object | None) -> dict[str, float]:
    merged = dict(CARD_WEIGHTS)
    if not isinstance(stored, dict):
        return merged
    editable = set(editable_card_ids())
    for card_id in editable:
        if card_id not in stored:
            continue
        try:
            weight = float(stored[card_id])
        except (TypeError, ValueError):
            continue
        if not math.isfinite(weight):
            continue
        merged[card_id] = max(0.0, min(5.0, weight))
    return merged


def validate_put_weights(raw: dict) -> dict[str, float]:
    if not isinstance(raw, dict):
        raise ValueError("weights 必须是对象")
    editable = set(editable_card_ids())
    out: dict[str, float] = {}
    for card_id, value in raw.items():
        if card_id not in editable:
            raise ValueError(f"未知或不可编辑的卡片：{card_id}")
        try:
            weight = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"权重必须是数字：{card_id}") from exc
        if not math.isfinite(weight):
            raise ValueError(f"权重必须是有限数字：{card_id}")
        if weight < 0 or weight > 5:
            raise ValueError("权重超出范围 [0, 5]")
        out[card_id] = round(weight, 2)
    return out


def meta_key(user_id: str) -> str:
    return f"radar/resonance_weights/{user_id}"


def load_user_weights(db: Session, user_id: str) -> dict[str, float]:
    raw = db.execute(
        text("SELECT value FROM app.meta WHERE key = :k"),
        {"k": meta_key(user_id)},
    ).scalar()
    if not raw:
        return merge_weights(None)
    try:
        stored = json.loads(raw)
    except (TypeError, ValueError, json.JSONDecodeError):
        return merge_weights(None)
    return merge_weights(stored)


def _editable_subset(validated: dict[str, float]) -> dict[str, float]:
    payload: dict[str, float] = {}
    for card_id in editable_card_ids():
        if card_id in validated:
            payload[card_id] = validated[card_id]
        else:
            payload[card_id] = CARD_WEIGHTS[card_id]
    return payload


def save_user_weights(db: Session, user_id: str, weights: dict) -> dict[str, float]:
    key = meta_key(user_id)
    if weights == {}:
        db.execute(text("DELETE FROM app.meta WHERE key = :k"), {"k": key})
        db.commit()
        return merge_weights(None)
    validated = validate_put_weights(weights)
    payload = _editable_subset(validated)
    db.execute(
        text(
            """
            INSERT INTO app.meta (key, value)
            VALUES (:k, :v)
            ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
            """
        ),
        {"k": key, "v": json.dumps(payload, ensure_ascii=False)},
    )
    db.commit()
    return merge_weights(payload)


def weights_payload(merged: dict[str, float]) -> RadarResonanceWeightsOut:
    items = [
        RadarResonanceWeightItem(
            card_id=card_id,
            title=CARD_TITLES.get(card_id, card_id),
            weight=merged[card_id],
            default_weight=CARD_WEIGHTS[card_id],
        )
        for card_id in editable_card_ids()
    ]
    return RadarResonanceWeightsOut(
        items=items,
        weights={card_id: merged[card_id] for card_id in editable_card_ids()},
    )


def _row_vt_symbol(row: dict[str, Any]) -> str:
    raw = str(row.get("vt_symbol") or "").strip()
    if raw:
        try:
            code, exch = parse_flexible_symbol(raw)
            return to_vt_symbol(code, exch)
        except ValueError:
            return raw.upper()
    tf = str(row.get("tf_symbol") or row.get("symbol") or "").strip()
    if not tf:
        return ""
    if "." in tf and tf.split(".", 1)[0] in {"SHSE", "SZSE", "BJSE"}:
        return _to_vt_symbol(tf)
    try:
        code, exch = parse_flexible_symbol(tf)
        return to_vt_symbol(code, exch)
    except ValueError:
        return ""


def _row_name(row: dict[str, Any]) -> str:
    return str(row.get("name") or "").strip()


def _row_seal_label(row: dict[str, Any], first_time_map: dict[str, str] | None) -> str:
    label = str(row.get("seal_time_label") or "").strip()
    if label:
        return label
    if not first_time_map:
        return ""
    for key in (
        row.get("vt_symbol"),
        row.get("tf_symbol"),
        row.get("symbol"),
    ):
        first_time = lookup_first_time(str(key or ""), first_time_map)
        if first_time:
            return format_seal_time_label(first_time)
    return ""


def _group_card_hits(
    cards: list[RadarCardOut],
    *,
    weights: dict[str, float] | None = None,
) -> dict[str, int]:
    """vt → 出现在几张有效权重卡。"""
    table = weights if weights is not None else CARD_WEIGHTS
    counts: dict[str, int] = {}
    for card in cards:
        weight = float(table.get(card.card_id, CARD_WEIGHTS.get(card.card_id, 1.0)))
        if weight <= 0:
            continue
        seen_in_card: set[str] = set()
        for row in card.rows:
            if not isinstance(row, dict):
                continue
            vt = _row_vt_symbol(row)
            if not vt or vt in seen_in_card:
                continue
            if vt.upper() in {"STAT", "TOTAL", "—", "-"}:
                continue
            seen_in_card.add(vt)
            counts[vt] = counts.get(vt, 0) + 1
    return counts


def resonance_scan_stats(
    cards: list[RadarCardOut],
    *,
    min_cards: int = 2,
    weights: dict[str, float] | None = None,
) -> tuple[int, int]:
    """返回 (scanned_total, excluded_count)。"""
    min_cards = max(1, min(int(min_cards), 10))
    counts = _group_card_hits(cards, weights=weights)
    scanned = len(counts)
    excluded = sum(1 for n in counts.values() if n < min_cards)
    return scanned, excluded


def compute_resonance(
    cards: list[RadarCardOut],
    *,
    min_cards: int = 2,
    top_n: int = 20,
    first_time_map: dict[str, str] | None = None,
    weights: dict[str, float] | None = None,
) -> RadarResonanceOut:
    min_cards = max(1, min(int(min_cards), 10))
    top_n = max(1, min(int(top_n), 100))
    ft_map = first_time_map or {}
    grouped: dict[str, dict[str, Any]] = {}

    table = weights if weights is not None else CARD_WEIGHTS
    for card in cards:
        weight = float(table.get(card.card_id, CARD_WEIGHTS.get(card.card_id, 1.0)))
        if weight <= 0:
            continue
        seen_in_card: set[str] = set()
        for row in card.rows:
            if not isinstance(row, dict):
                continue
            vt = _row_vt_symbol(row)
            if not vt or vt in seen_in_card:
                continue
            # 统计/板块伪行
            if vt.upper() in {"STAT", "TOTAL", "—", "-"}:
                continue
            seen_in_card.add(vt)
            bucket = grouped.setdefault(
                vt,
                {
                    "name": "",
                    "titles": [],
                    "card_count": 0,
                    "weight_score": 0.0,
                    "change_pct": None,
                    "last_price": None,
                    "seal_time_label": "",
                },
            )
            if not bucket["name"]:
                bucket["name"] = _row_name(row)
            titles: list[str] = bucket["titles"]
            titles.append(card.title or card.card_id)
            bucket["card_count"] = int(bucket["card_count"]) + 1
            bucket["weight_score"] = float(bucket["weight_score"]) + weight
            if row.get("change_pct") is not None and bucket["change_pct"] is None:
                with suppress(TypeError, ValueError):
                    bucket["change_pct"] = float(row["change_pct"])
            if row.get("last_price") is not None and bucket["last_price"] is None:
                with suppress(TypeError, ValueError):
                    bucket["last_price"] = float(row["last_price"])
            if not bucket["seal_time_label"]:
                bucket["seal_time_label"] = _row_seal_label(row, ft_map)

    entries: list[RadarResonanceEntry] = []
    for vt, bucket in grouped.items():
        card_count = int(bucket["card_count"])
        if card_count < min_cards:
            continue
        seal_label = str(bucket["seal_time_label"] or "")
        if not seal_label and ft_map:
            seal_label = format_seal_time_label(lookup_first_time(vt, ft_map))
        entries.append(
            RadarResonanceEntry(
                vt_symbol=vt,
                name=str(bucket["name"] or ""),
                card_count=card_count,
                card_titles=list(bucket["titles"]),
                resonance_score=round(float(bucket["weight_score"]), 2),
                change_pct=bucket["change_pct"],
                last_price=bucket["last_price"],
                seal_time_label=seal_label,
            )
        )
    entries.sort(key=lambda e: (-e.resonance_score, -e.card_count, e.vt_symbol))
    entries = entries[:top_n]
    return RadarResonanceOut(
        min_cards=min_cards,
        top_n=top_n,
        total=len(entries),
        entries=entries,
    )


def list_radar_resonance(
    db: Session,
    *,
    user_id: str,
    min_cards: int = 2,
    top_n: int = 20,
) -> RadarResonanceOut:
    from app.domains.market.limit_list_store import load_first_time_map

    cards = list_radar_cards(db)
    first_time_map = load_first_time_map(db)
    user_weights = load_user_weights(db, user_id)
    return compute_resonance(
        cards,
        min_cards=min_cards,
        top_n=top_n,
        first_time_map=first_time_map,
        weights=user_weights,
    )

"""雷达卡片：优先读 cache.radar_card_snapshot，不足时用 PG/Redis 合成。"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.market import RadarCardSnapshot
from app.schemas.market import RadarCardOut
from app.services import market as market_svc
from app.services import sector as sector_svc
from app.services.quotes import get_quote_store


def _from_cache(db: Session) -> list[RadarCardOut]:
    rows = db.scalars(select(RadarCardSnapshot))
    out: list[RadarCardOut] = []
    for row in rows:
        try:
            payload = json.loads(row.payload_json or "{}")
        except json.JSONDecodeError:
            payload = {}
        if not isinstance(payload, dict):
            payload = {}
        out.append(
            RadarCardOut(
                card_id=row.card_id,
                title=str(payload.get("title") or row.card_id),
                subtitle=str(payload.get("subtitle") or ""),
                source="cache",
                computed_at=row.computed_at,
                empty_message=str(payload.get("empty_message") or ""),
                rows=list(payload.get("rows") or []),
            )
        )
    return out


def _synth_sector_hot(db: Session) -> RadarCardOut:
    rows = sector_svc.list_sector_flow(db, kind="concept", sort="net_flow_yi", limit=15)
    return RadarCardOut(
        card_id="sector_flow_hot",
        title="板块·资金热力",
        subtitle=rows[0].trade_date if rows else "",
        source="synthesized",
        rows=[
            {
                "name": r.name,
                "sector_id": r.sector_id,
                "sector_kind": r.sector_kind,
                "net_flow_yi": r.net_flow_yi,
                "change_pct": r.change_pct,
            }
            for r in rows
        ],
        empty_message="" if rows else "暂无板块资金数据",
    )


def _synth_limit_ladder(db: Session) -> RadarCardOut:
    emotion = market_svc.load_emotion(db)
    if not emotion:
        return RadarCardOut(
            card_id="discovery_limit_ladder",
            title="发现·连板梯队",
            source="synthesized",
            empty_message="暂无连板梯队数据",
        )
    rows: list[dict[str, Any]] = []
    if emotion.max_board_vt_symbol:
        rows.append(
            {
                "vt_symbol": emotion.max_board_vt_symbol,
                "limit_times": emotion.max_limit_times,
                "role": "最高板",
            }
        )
    for vt in emotion.linked_board_vt_symbols:
        if vt == emotion.max_board_vt_symbol:
            continue
        rows.append({"vt_symbol": vt, "role": "关联"})
    if rows:
        from app.services.limit_list_store import attach_first_time_fields, load_first_time_map

        trade_date = str(emotion.trade_date or "") or None
        attach_first_time_fields(rows, load_first_time_map(db, trade_date))
    return RadarCardOut(
        card_id="discovery_limit_ladder",
        title="发现·连板梯队",
        subtitle=str(emotion.trade_date or ""),
        source="synthesized",
        computed_at=str(emotion.updated_at or ""),
        rows=rows[:40],
    )


def _synth_change_top() -> RadarCardOut:
    store = get_quote_store()
    if not store.available():
        return RadarCardOut(
            card_id="discovery_change_top",
            title="发现·涨幅榜",
            source="synthesized",
            empty_message="Redis 不可用",
        )
    ranked = store.list_rank("change_pct", top_n=20)
    if not ranked:
        return RadarCardOut(
            card_id="discovery_change_top",
            title="发现·涨幅榜",
            source="synthesized",
            empty_message="行情快照为空，请启动 quote-collector",
        )
    quotes = {q.symbol: q for q in store.get_quotes([s for s, _ in ranked])}
    rows = []
    for tf, score in ranked:
        q = quotes.get(tf)
        rows.append(
            {
                "tf_symbol": tf,
                "name": q.name if q else "",
                "change_pct": float(score),
                "last_price": q.last_price if q else None,
            }
        )
    return RadarCardOut(
        card_id="discovery_change_top",
        title="发现·涨幅榜",
        source="synthesized",
        rows=rows,
    )


def _synth_limit_break(db: Session) -> RadarCardOut | None:
    from app.services.limit_list_store import list_limit_list

    payload = list_limit_list(db, lazy_fetch=False)
    rows_in = list(payload.rows or [])
    rows: list[dict[str, Any]] = []
    for item in rows_in:
        try:
            open_times = float(item.open_times or 0)
        except (TypeError, ValueError):
            open_times = 0.0
        if open_times <= 0:
            continue
        vt = str(item.vt_symbol or "").strip()
        if not vt:
            continue
        rows.append(
            {
                "vt_symbol": vt,
                "name": str(item.name or ""),
                "open_times": open_times,
                "limit_times": item.limit_times,
                "seal_time_label": str(item.seal_time_label or ""),
            }
        )
    rows.sort(key=lambda r: (-float(r["open_times"]), str(r["vt_symbol"])))
    rows = rows[:30]
    if not rows:
        return None
    return RadarCardOut(
        card_id="discovery_limit_break",
        title="发现·炸板断板",
        subtitle=str(payload.trade_date or ""),
        source="synthesized",
        rows=rows,
    )


def _synth_volume_surge() -> RadarCardOut | None:
    from app.services.quotes import _to_vt_symbol

    store = get_quote_store()
    if not store.available():
        return None
    ranked = store.list_rank("volume_ratio", top_n=80)
    filtered = [(tf, score) for tf, score in ranked if float(score) >= 2.0]
    if not filtered:
        return None
    filtered = filtered[:30]
    quotes = {q.symbol: q for q in store.get_quotes([s for s, _ in filtered])}
    rows: list[dict[str, Any]] = []
    for tf, score in filtered:
        q = quotes.get(tf)
        vt = ""
        try:
            vt = _to_vt_symbol(tf) if "." in tf and tf.split(".", 1)[0] in {"SHSE", "SZSE", "BJSE"} else ""
        except Exception:
            vt = ""
        if not vt:
            vt = str(tf)
        rows.append(
            {
                "tf_symbol": tf,
                "vt_symbol": vt,
                "name": q.name if q else "",
                "volume_ratio": float(score),
                "change_pct": q.change_pct if q else None,
                "last_price": q.last_price if q else None,
            }
        )
    return RadarCardOut(
        card_id="discovery_volume_surge",
        title="发现·放量异动",
        source="synthesized",
        rows=rows,
    )


def _synth_leader_pick(db: Session) -> RadarCardOut:
    from app.services import leader_screen

    rows, subtitle, empty = leader_screen.synth_leader_pick_rows(db, top_n=12, variant="mainline")
    return RadarCardOut(
        card_id="leader_pick",
        title="选股·龙头",
        subtitle=subtitle,
        source="synthesized",
        rows=rows,
        empty_message=empty,
    )


def build_synthesized_cards(db: Session) -> list[RadarCardOut]:
    cards = [
        _synth_leader_pick(db),
        _synth_limit_ladder(db),
        _synth_sector_hot(db),
        _synth_change_top(),
    ]
    limit_break = _synth_limit_break(db)
    if limit_break is not None:
        cards.append(limit_break)
    volume_surge = _synth_volume_surge()
    if volume_surge is not None:
        cards.append(volume_surge)
    return cards


def list_radar_cards(db: Session) -> list[RadarCardOut]:
    cached = {c.card_id: c for c in _from_cache(db)}
    synthesized = build_synthesized_cards(db)
    # cache 优先；合成补缺
    out: list[RadarCardOut] = []
    seen: set[str] = set()
    for card in list(cached.values()) + synthesized:
        if card.card_id in seen:
            continue
        seen.add(card.card_id)
        out.append(card)
    # 稳定顺序：龙头/发现/板块/自选
    priority = {
        "leader_pick": 0,
        "discovery_limit_ladder": 1,
        "discovery_limit_break": 2,
        "discovery_volume_surge": 3,
        "discovery_change_top": 4,
        "sector_flow_hot": 5,
        "watchlist_short_term": 6,
    }
    out.sort(key=lambda c: priority.get(c.card_id, 50))
    return out


def get_radar_card(db: Session, card_id: str) -> RadarCardOut | None:
    for card in list_radar_cards(db):
        if card.card_id == card_id:
            return card
    return None

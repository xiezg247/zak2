"""雷达共振配方：跨卡共振 → screener_runs。"""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.schemas.market import RadarResonanceEntry
from app.schemas.screener import HardFilterPrefs
from app.services.market.quotes import QuoteRow
from app.services.radar.cards import list_radar_cards
from app.services.radar.radar_resonance import list_radar_resonance
from app.services.symbols import parse_flexible_symbol, to_tf_symbol


def _entry_to_quote_row(entry: RadarResonanceEntry) -> QuoteRow:
    code, exch = parse_flexible_symbol(entry.vt_symbol)
    tf = to_tf_symbol(code, exch)
    row = QuoteRow(
        symbol=tf,
        name=entry.name or "",
        change_pct=float(entry.change_pct or 0.0),
        last_price=float(entry.last_price or 0.0),
    )
    titles = "、".join(entry.card_titles) if entry.card_titles else f"{entry.card_count}卡"
    row.__dict__["_score"] = float(entry.resonance_score)
    row.__dict__["_hit_reason"] = f"共振 加权{entry.resonance_score:g}：{titles}"
    if entry.seal_time_label:
        row.__dict__["_seal_time_label"] = entry.seal_time_label
    return row


def run_resonance_screen(
    *,
    db: Session,
    user_id: str,
    top_n: int = 20,
    hard_filter: HardFilterPrefs,
    previous_symbols: set[str] | None = None,
) -> dict[str, Any]:
    from app.services.screener.engine import _pack_result

    if not user_id:
        raise HTTPException(status_code=400, detail="雷达共振需要登录用户")
    cards = list_radar_cards(db)
    if not cards:
        raise HTTPException(status_code=400, detail="暂无雷达卡片，请先打开雷达页刷新")

    resonance = list_radar_resonance(db, user_id=user_id, min_cards=2, top_n=top_n)
    quote_rows = [_entry_to_quote_row(e) for e in resonance.entries]
    # 本刀跳过硬过滤（spec 允许）
    condition = "雷达共振"
    if not quote_rows:
        condition = "雷达共振 · 暂无共振（跨卡≥2）"

    result = _pack_result(
        quote_rows,
        total_scanned=len(quote_rows),
        condition=condition,
        source="radar_resonance",
        config={
            "recipe_id": "radar_resonance",
            "top_n": top_n,
            "min_cards": 2,
            "hard_filter_skipped": True,
        },
        previous_symbols=previous_symbols,
        hard_filter=hard_filter,
    )
    for packed, src in zip(result["rows"], quote_rows, strict=True):
        label = src.__dict__.get("_seal_time_label")
        if label:
            packed["seal_time_label"] = label
    return result

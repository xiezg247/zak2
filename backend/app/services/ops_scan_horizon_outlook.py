"""雷达展望：共振启发式写入 cache.radar_horizon_cache。"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.ops_scheduler import save_job_run_meta
from app.services.radar import list_radar_cards
from app.services.radar_resonance import compute_resonance

JOB_ID = "scan_horizon_outlook"
STRATEGY_KEY = "resonance_heuristic"
VARIANT = "default"
TOP_N = 30
MIN_CARDS = 2


def _now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _upsert_horizon(
    db: Session,
    *,
    rows: list[dict[str, Any]],
    scanned_total: int,
    refined_total: int,
    computed_at: str,
) -> None:
    db.execute(
        text(
            """
            INSERT INTO cache.radar_horizon_cache (
                variant, rows_json, scanned_total, excluded_count,
                prefilter_total, refined_total, kline_missing, strategy_key, computed_at
            ) VALUES (
                :variant, :rows_json, :scanned_total, 0,
                :prefilter_total, :refined_total, 0, :strategy_key, :computed_at
            )
            ON CONFLICT (variant) DO UPDATE SET
                rows_json = EXCLUDED.rows_json,
                scanned_total = EXCLUDED.scanned_total,
                excluded_count = EXCLUDED.excluded_count,
                prefilter_total = EXCLUDED.prefilter_total,
                refined_total = EXCLUDED.refined_total,
                kline_missing = EXCLUDED.kline_missing,
                strategy_key = EXCLUDED.strategy_key,
                computed_at = EXCLUDED.computed_at
            """
        ),
        {
            "variant": VARIANT,
            "rows_json": json.dumps(rows, ensure_ascii=False),
            "scanned_total": scanned_total,
            "prefilter_total": scanned_total,
            "refined_total": refined_total,
            "strategy_key": STRATEGY_KEY,
            "computed_at": computed_at,
        },
    )


def scan_horizon_outlook(db: Session) -> dict[str, Any]:
    cards = list_radar_cards(db)
    resonance = compute_resonance(cards, min_cards=MIN_CARDS, top_n=TOP_N)
    rows = [
        {
            "vt_symbol": e.vt_symbol,
            "name": e.name,
            "resonance_score": e.resonance_score,
            "card_count": e.card_count,
            "card_titles": e.card_titles,
            "change_pct": e.change_pct,
            "last_price": e.last_price,
            "seal_time_label": e.seal_time_label or "",
        }
        for e in resonance.entries
    ]
    scanned = sum(len(c.rows or []) for c in cards)
    computed_at = _now_iso()
    _upsert_horizon(
        db,
        rows=rows,
        scanned_total=scanned,
        refined_total=len(rows),
        computed_at=computed_at,
    )
    db.commit()
    msg = f"启发式展望已写入 {len(rows)} 条（resonance_heuristic）"
    if not rows:
        msg = "启发式展望已写入 0 条（无达标共振标的）"
    save_job_run_meta(db, JOB_ID, last_message=msg, last_success=True)
    return {
        "success": True,
        "skipped": False,
        "message": msg,
        "written": len(rows),
        "strategy_key": STRATEGY_KEY,
    }

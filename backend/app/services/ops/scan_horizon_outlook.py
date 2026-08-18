"""雷达展望：共振启发式 + 规则预测两阶段写入 cache。"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.schemas.ops import SyncResult
from app.services.market.limit_list_store import load_first_time_map
from app.services.ops.scheduler import save_job_run_meta
from app.services.radar.cards import list_radar_cards
from app.services.radar.radar_predict import (
    MODEL_LABEL,
    score_predict_rows,
    upsert_predict,
    vt_with_min_daily_bars,
)
from app.services.radar.radar_resonance import compute_resonance, resonance_scan_stats

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
    excluded_count: int,
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
                :variant, :rows_json, :scanned_total, :excluded_count,
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
            "excluded_count": excluded_count,
            "prefilter_total": scanned_total,
            "refined_total": refined_total,
            "strategy_key": STRATEGY_KEY,
            "computed_at": computed_at,
        },
    )


def scan_horizon_outlook(db: Session) -> SyncResult:
    computed_at = _now_iso()
    cards = list_radar_cards(db)
    ft = load_first_time_map(db)
    scanned_total, excluded_count = resonance_scan_stats(cards, min_cards=MIN_CARDS)
    resonance = compute_resonance(cards, min_cards=MIN_CARDS, top_n=TOP_N, first_time_map=ft)
    rows: list[dict[str, Any]] = [
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
    _upsert_horizon(
        db,
        rows=rows,
        scanned_total=scanned_total,
        excluded_count=excluded_count,
        refined_total=len(rows),
        computed_at=computed_at,
    )
    db.commit()

    predict_written = 0
    predict_error: str | None = None
    try:
        has_bars = vt_with_min_daily_bars(db, [r["vt_symbol"] for r in rows], min_bars=5)
        predict_rows, kline_missing = score_predict_rows(rows, has_daily_bars=has_bars, top_n=TOP_N)
        upsert_predict(
            db,
            rows=predict_rows,
            scanned_total=len(rows),
            refined_total=len(predict_rows),
            kline_missing=kline_missing,
            computed_at=computed_at,
        )
        db.commit()
        predict_written = len(predict_rows)
    except Exception as exc:
        db.rollback()
        predict_error = str(exc)[:200]

    parts = [
        f"horizon={len(rows)}",
        f"predict={predict_written}",
        f"model={MODEL_LABEL}",
        f"scanned={scanned_total}",
        f"excluded={excluded_count}",
    ]
    if not cards:
        parts.append("无雷达卡片，可先 warm_radar_card_snapshots")
    if predict_error:
        parts.append(f"predict_error={predict_error}")
    message = "；".join(parts)

    save_job_run_meta(db, JOB_ID, last_success=True, last_message=message)
    return SyncResult(
        success=True,
        message=message,
        extra={
            "written": len(rows),
            "horizon_written": len(rows),
            "predict_written": predict_written,
            "predict_error": predict_error,
            "strategy_key": STRATEGY_KEY,
            "model_label": MODEL_LABEL,
        },
    )

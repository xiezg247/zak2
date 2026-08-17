"""雷达卡片快照预热：合成卡片 → cache.radar_card_snapshot。"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.schemas.market import RadarCardOut
from app.schemas.ops import SyncResult
from app.services.ops.scheduler import save_job_run_meta
from app.services.radar import build_synthesized_cards

JOB_ID = "warm_radar_card_snapshots"


def _now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _card_payload(card: RadarCardOut) -> dict[str, Any]:
    return {
        "title": card.title,
        "subtitle": card.subtitle,
        "rows": card.rows,
        "empty_message": card.empty_message,
    }


def _upsert_card(db: Session, *, card_id: str, payload: dict[str, Any], computed_at: str) -> None:
    db.execute(
        text(
            """
            INSERT INTO cache.radar_card_snapshot (card_id, variant_key, payload_json, computed_at)
            VALUES (:card_id, '', :payload_json, :computed_at)
            ON CONFLICT (card_id, variant_key) DO UPDATE SET
                payload_json = EXCLUDED.payload_json,
                computed_at = EXCLUDED.computed_at
            """
        ),
        {
            "card_id": card_id,
            "payload_json": json.dumps(payload, ensure_ascii=False),
            "computed_at": computed_at,
        },
    )


def warm_radar_card_snapshots(db: Session) -> SyncResult:
    cards = build_synthesized_cards(db)
    computed_at = _now_iso()
    for card in cards:
        _upsert_card(db, card_id=card.card_id, payload=_card_payload(card), computed_at=computed_at)

    db.commit()
    message = f"雷达卡片预热 {len(cards)} 张"
    save_job_run_meta(db, JOB_ID, last_message=message, last_success=True)
    return SyncResult(success=True, message=message, extra={"written": len(cards)})

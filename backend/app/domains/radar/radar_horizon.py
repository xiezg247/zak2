"""读 cache.radar_horizon_cache 启发式展望。"""

from __future__ import annotations

import json

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.domains.market.schemas import RadarHorizonOut, RadarHorizonRow


def load_horizon(db: Session, *, variant: str = "default") -> RadarHorizonOut:
    row = (
        db.execute(
            text(
                """
                SELECT variant, rows_json, scanned_total, refined_total, strategy_key, computed_at
                FROM cache.radar_horizon_cache
                WHERE variant = :variant
                """
            ),
            {"variant": variant},
        )
        .mappings()
        .first()
    )
    if not row:
        return RadarHorizonOut(variant=variant, empty=True)

    raw_rows = json.loads(row["rows_json"] or "[]")
    rows = [RadarHorizonRow(**item) for item in raw_rows]
    computed_at = row["computed_at"]
    return RadarHorizonOut(
        variant=str(row["variant"]),
        strategy_key=str(row["strategy_key"] or ""),
        computed_at=str(computed_at) if computed_at else None,
        scanned_total=int(row["scanned_total"] or 0),
        refined_total=int(row["refined_total"] or 0),
        rows=rows,
        empty=not rows,
    )

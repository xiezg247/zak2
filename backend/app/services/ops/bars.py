"""本地日 K overview（public.dbbaroverview 只读）。"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session


def bars_overview(db: Session, *, interval: str = "d") -> dict[str, Any]:
    row = (
        db.execute(
            text(
                """
            WITH latest AS (
              SELECT cal_date
              FROM app.trade_calendar
              WHERE is_open = 1 AND cal_date <= CURRENT_DATE::text
              ORDER BY cal_date DESC
              LIMIT 1
            ),
            valid AS (
              SELECT
                o.symbol,
                o.exchange,
                (o."end")::date AS end_d,
                o.start,
                o."end",
                o.count
              FROM public.dbbaroverview o
              WHERE o.interval = :interval
                AND o.exchange IS NOT NULL
                AND o.start IS NOT NULL
                AND o."end" IS NOT NULL
                AND o.count > 0
            )
            SELECT
              (SELECT COUNT(*) FROM valid) AS symbol_count,
              (SELECT MIN(start) FROM valid) AS min_start,
              (SELECT MAX("end") FROM valid) AS max_end,
              (SELECT cal_date FROM latest) AS as_of_trade_date,
              (SELECT COUNT(*) FROM valid, latest
               WHERE end_d >= CAST(latest.cal_date AS date)) AS ok_count,
              (SELECT COUNT(*) FROM valid, latest
               WHERE end_d < CAST(latest.cal_date AS date)) AS stale_count
            """
            ),
            {"interval": interval},
        )
        .mappings()
        .first()
    )

    if not row:
        return {
            "interval": interval,
            "symbol_count": 0,
            "min_start": None,
            "max_end": None,
            "as_of_trade_date": None,
            "ok_count": 0,
            "stale_count": 0,
        }

    def _iso(v: Any) -> str | None:
        if v is None:
            return None
        if hasattr(v, "isoformat"):
            return v.isoformat()
        return str(v)

    symbol_count = int(row["symbol_count"] or 0)
    ok_count = int(row["ok_count"] or 0)
    stale_count = int(row["stale_count"] or 0)
    # 无日历时 COUNT 与 latest 笛卡尔为空，回退全量未知
    if not row["as_of_trade_date"] and symbol_count:
        ok_count = 0
        stale_count = 0

    return {
        "interval": interval,
        "symbol_count": symbol_count,
        "min_start": _iso(row["min_start"]),
        "max_end": _iso(row["max_end"]),
        "as_of_trade_date": row["as_of_trade_date"],
        "ok_count": ok_count,
        "stale_count": stale_count,
        "unknown_count": max(0, symbol_count - ok_count - stale_count),
    }

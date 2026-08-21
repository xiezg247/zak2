"""规则预测：打分、日 K 存在性、cache 读写。"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.domains.watchlist.repository import resolve_symbol_pair
from app.domains.market.schemas import RadarPredictOut, RadarPredictRow

MODEL_LABEL = "rules_v1"
VARIANT = "default"


def score_predict_rows(
    horizon_rows: list[dict[str, Any]],
    *,
    has_daily_bars: set[str],
    top_n: int = 30,
) -> tuple[list[dict[str, Any]], int]:
    scored: list[dict[str, Any]] = []
    kline_missing = 0
    for raw in horizon_rows:
        vt = str(raw.get("vt_symbol") or "").strip()
        if not vt:
            continue
        resonance_score = float(raw.get("resonance_score") or 0)
        card_count = int(raw.get("card_count") or 0)
        change_pct = raw.get("change_pct")
        if change_pct is not None:
            try:
                change_pct = float(change_pct)
            except (TypeError, ValueError):
                change_pct = None
        seal = str(raw.get("seal_time_label") or "").strip()
        titles = list(raw.get("card_titles") or [])

        score = float(resonance_score)
        reasons: list[str] = [f"共振 {resonance_score}"]
        if card_count >= 4:
            score += 1.0
            reasons.append("出现≥4卡")
        elif card_count >= 3:
            score += 0.5
            reasons.append("出现≥3卡")
        if change_pct is not None:
            if change_pct >= 7:
                score += 0.8
                reasons.append("涨幅≥7%")
            elif change_pct >= 3:
                score += 0.4
                reasons.append("涨幅≥3%")
            elif change_pct < 0:
                score -= 0.5
                reasons.append("涨幅为负")
        if seal:
            score += 0.6
            reasons.append("有封板时刻")
        if vt in has_daily_bars:
            score += 0.3
            reasons.append("近5日K可用")
        else:
            kline_missing += 1

        scored.append(
            {
                "vt_symbol": vt,
                "name": str(raw.get("name") or ""),
                "predict_score": round(score, 4),
                "resonance_score": resonance_score,
                "card_count": card_count,
                "card_titles": titles,
                "change_pct": change_pct,
                "last_price": raw.get("last_price"),
                "seal_time_label": seal,
                "reasons": reasons,
            }
        )

    scored.sort(key=lambda r: (-float(r["predict_score"]), -float(r["resonance_score"]), r["vt_symbol"]))
    return scored[: max(1, int(top_n))], kline_missing


def vt_with_min_daily_bars(db: Session, vt_symbols: list[str], *, min_bars: int = 5) -> set[str]:
    if not vt_symbols:
        return set()
    pairs: list[tuple[str, str, str]] = []
    for vt in vt_symbols:
        try:
            symbol, exchange = resolve_symbol_pair(vt)
        except Exception:
            continue
        pairs.append((vt, symbol, exchange))
    if not pairs:
        return set()

    # 批量：按 (symbol, exchange) 计数
    found: set[str] = set()
    # chunk to keep SQL manageable
    chunk = 50
    for i in range(0, len(pairs), chunk):
        part = pairs[i : i + chunk]
        conditions = []
        params: dict[str, Any] = {"min_bars": int(min_bars)}
        for j, (_vt, symbol, exchange) in enumerate(part):
            conditions.append(f"(symbol = :s{j} AND exchange = :e{j})")
            params[f"s{j}"] = symbol
            params[f"e{j}"] = exchange
        sql = f"""
            SELECT symbol, exchange, COUNT(*) AS n
            FROM public.dbbardata
            WHERE interval = 'd' AND ({" OR ".join(conditions)})
            GROUP BY symbol, exchange
            HAVING COUNT(*) >= :min_bars
        """
        rows = db.execute(text(sql), params).mappings().all()
        hit = {(str(r["symbol"]), str(r["exchange"])) for r in rows}
        for vt, symbol, exchange in part:
            if (symbol, exchange) in hit:
                found.add(vt)
    return found


def upsert_predict(
    db: Session,
    *,
    rows: list[dict[str, Any]],
    scanned_total: int,
    refined_total: int,
    kline_missing: int,
    computed_at: str,
    variant: str = VARIANT,
    model_label: str = MODEL_LABEL,
) -> None:
    db.execute(
        text(
            """
            INSERT INTO cache.radar_predict_cache (
                variant, rows_json, scanned_total, excluded_count,
                prefilter_total, refined_total, kline_missing, model_label, computed_at
            ) VALUES (
                :variant, :rows_json, :scanned_total, 0,
                :prefilter_total, :refined_total, :kline_missing, :model_label, :computed_at
            )
            ON CONFLICT (variant) DO UPDATE SET
                rows_json = EXCLUDED.rows_json,
                scanned_total = EXCLUDED.scanned_total,
                excluded_count = EXCLUDED.excluded_count,
                prefilter_total = EXCLUDED.prefilter_total,
                refined_total = EXCLUDED.refined_total,
                kline_missing = EXCLUDED.kline_missing,
                model_label = EXCLUDED.model_label,
                computed_at = EXCLUDED.computed_at
            """
        ),
        {
            "variant": variant,
            "rows_json": json.dumps(rows, ensure_ascii=False),
            "scanned_total": int(scanned_total),
            "prefilter_total": int(scanned_total),
            "refined_total": int(refined_total),
            "kline_missing": int(kline_missing),
            "model_label": model_label,
            "computed_at": computed_at,
        },
    )


def load_predict(db: Session, *, variant: str = VARIANT) -> RadarPredictOut:
    row = (
        db.execute(
            text(
                """
                SELECT variant, rows_json, scanned_total, refined_total, kline_missing,
                       model_label, computed_at
                FROM cache.radar_predict_cache
                WHERE variant = :variant
                """
            ),
            {"variant": variant},
        )
        .mappings()
        .first()
    )
    if not row:
        return RadarPredictOut(variant=variant, empty=True)

    raw_rows = json.loads(row["rows_json"] or "[]")
    rows = [RadarPredictRow(**item) for item in raw_rows]
    computed_at = row["computed_at"]
    return RadarPredictOut(
        variant=str(row["variant"]),
        model_label=str(row["model_label"] or ""),
        computed_at=str(computed_at) if computed_at else None,
        scanned_total=int(row["scanned_total"] or 0),
        refined_total=int(row["refined_total"] or 0),
        kline_missing=int(row["kline_missing"] or 0),
        rows=rows,
        empty=not rows,
    )


def now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()

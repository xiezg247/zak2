"""交易风控偏好（auth.user_preferences trading/risk，与桌面同表）。"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

NAMESPACE = "trading"
PREF_KEY = "risk"

DEFAULT_STOP_LOSS_PCT = 0.05
DEFAULT_CAUTION_FLOAT_PCT = -5.0

_PREF_FIELDS = (
    "total_capital",
    "stop_loss_pct",
    "caution_float_pct",
    "realized_pnl_today",
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _default_prefs() -> dict[str, Any]:
    return {
        "total_capital": None,
        "stop_loss_pct": DEFAULT_STOP_LOSS_PCT,
        "caution_float_pct": DEFAULT_CAUTION_FLOAT_PCT,
        "realized_pnl_today": None,
    }


def normalize_prefs(raw: dict[str, Any]) -> dict[str, Any]:
    base = _default_prefs()
    merged = {**base, **{k: raw.get(k, base[k]) for k in _PREF_FIELDS}}

    stop_loss = merged["stop_loss_pct"]
    if not isinstance(stop_loss, (int, float)) or stop_loss <= 0 or stop_loss > 0.5:
        stop_loss = DEFAULT_STOP_LOSS_PCT

    total = merged["total_capital"]
    if total is not None and (not isinstance(total, (int, float)) or total <= 0):
        total = None

    caution = merged["caution_float_pct"]
    if not isinstance(caution, (int, float)) or caution >= 0:
        caution = DEFAULT_CAUTION_FLOAT_PCT

    realized = merged["realized_pnl_today"]
    if realized is not None and not isinstance(realized, (int, float)):
        realized = None

    return {
        "total_capital": float(total) if total is not None else None,
        "stop_loss_pct": float(stop_loss),
        "caution_float_pct": float(caution),
        "realized_pnl_today": float(realized) if realized is not None else None,
    }


def _validate_merged(prefs: dict[str, Any]) -> None:
    total = prefs.get("total_capital")
    if total is not None and (not isinstance(total, (int, float)) or total <= 0):
        raise ValueError("总资金须为空或大于 0")

    stop_loss = prefs.get("stop_loss_pct")
    if not isinstance(stop_loss, (int, float)) or stop_loss <= 0 or stop_loss > 0.5:
        raise ValueError("止损比例须在 (0, 0.5] 范围内")

    caution = prefs.get("caution_float_pct")
    if not isinstance(caution, (int, float)) or caution >= 0:
        raise ValueError("浮亏警戒比例须小于 0")

    realized = prefs.get("realized_pnl_today")
    if realized is not None and not isinstance(realized, (int, float)):
        raise ValueError("当日已实现盈亏须为数值或空")


def load_trading_risk_prefs(db: Session, user_id: str) -> dict[str, Any]:
    row = db.execute(
        text(
            """
            SELECT value_json FROM auth.user_preferences
            WHERE user_id = CAST(:uid AS uuid)
              AND namespace = :ns AND key = :key
            LIMIT 1
            """
        ),
        {"uid": user_id, "ns": NAMESPACE, "key": PREF_KEY},
    ).scalar()
    if not isinstance(row, dict):
        return normalize_prefs({})
    return normalize_prefs(row)


def save_trading_risk_prefs(db: Session, user_id: str, body: dict[str, Any]) -> dict[str, Any]:
    current = load_trading_risk_prefs(db, user_id)
    merged = {**current, **{k: body[k] for k in body if k in _PREF_FIELDS}}
    _validate_merged(merged)
    normalized = normalize_prefs(merged)
    db.execute(
        text(
            """
            INSERT INTO auth.user_preferences (user_id, namespace, key, value_json, updated_at)
            VALUES (CAST(:uid AS uuid), :ns, :key, CAST(:val AS jsonb), CAST(:now AS timestamptz))
            ON CONFLICT (user_id, namespace, key)
            DO UPDATE SET value_json = EXCLUDED.value_json, updated_at = EXCLUDED.updated_at
            """
        ),
        {
            "uid": user_id,
            "ns": NAMESPACE,
            "key": PREF_KEY,
            "val": json.dumps(normalized, ensure_ascii=False),
            "now": _now_iso(),
        },
    )
    db.commit()
    return normalized


def compute_actual_position_pct(total_mv: float, total_capital: float | None) -> float | None:
    if total_capital is None or total_capital <= 0:
        return None
    return float(total_mv) / float(total_capital)


def normalize_plan_max_pct(raw: float) -> float | None:
    if raw <= 0:
        return None
    if raw > 1:
        return float(raw) / 100.0
    return float(raw)

"""情绪周期判定阈值（全局 app.meta 持久化）。"""

from __future__ import annotations

import json
import math
from dataclasses import asdict, fields
from typing import Any, NamedTuple

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.emotion.emotion_cycle import DEFAULT_THRESHOLDS, Thresholds
from app.services.emotion.emotion_cycle_cache import cache_invalidate

META_KEY = "emotion_cycle_thresholds"

THRESHOLDS_FIELDS = tuple(f.name for f in fields(Thresholds))

_INT_FIELDS = frozenset(
    {
        "recession_limit_down",
        "ice_max_boards",
        "ice_limit_down",
        "climax_ladder_depth",
        "climax_limit_up",
        "divergence_limit_up_min",
        "divergence_limit_spread",
        "startup_max_boards",
        "startup_limit_up",
    }
)
_RATIO_0_1_FIELDS = frozenset({"ice_up_ratio_max", "recession_break_rate"})
_FEAR_0_100_FIELDS = frozenset({"fear_greed_overheat"})
_FLOAT_GE0_FIELDS = frozenset({"amount_floor_yuan"})
_BOOL_FIELDS = frozenset({"hysteresis_enabled"})


def thresholds_to_dict(t: Thresholds) -> dict[str, Any]:
    return asdict(t)


def _clamp_field(name: str, value: Any) -> Any | None:
    if name in _BOOL_FIELDS:
        if isinstance(value, bool):
            return value
        if isinstance(value, int) and value in (0, 1):
            return bool(value)
        return None
    if name in _INT_FIELDS:
        try:
            n = int(value)
        except (TypeError, ValueError):
            return None
        return max(0, n)
    if name in _RATIO_0_1_FIELDS:
        try:
            f = float(value)
        except (TypeError, ValueError):
            return None
        if not math.isfinite(f):
            return None
        return max(0.0, min(1.0, f))
    if name in _FEAR_0_100_FIELDS:
        try:
            f = float(value)
        except (TypeError, ValueError):
            return None
        if not math.isfinite(f):
            return None
        return max(0.0, min(100.0, f))
    if name in _FLOAT_GE0_FIELDS:
        try:
            f = float(value)
        except (TypeError, ValueError):
            return None
        if not math.isfinite(f):
            return None
        return max(0.0, f)
    return None


def merge_thresholds(base: Thresholds, patch: dict) -> Thresholds:
    if not isinstance(patch, dict):
        return base
    updates: dict[str, Any] = {}
    for key, value in patch.items():
        if key not in THRESHOLDS_FIELDS:
            continue
        clamped = _clamp_field(key, value)
        if clamped is None:
            continue
        updates[key] = clamped
    if not updates:
        return base
    return Thresholds(**{**asdict(base), **updates})


class StoredBlob(NamedTuple):
    """meta 表中阈值 blob 的读取结果：值 + 是否回退默认。"""

    value: dict[str, Any] | None
    is_default: bool


class ThresholdsLoad(NamedTuple):
    """load_thresholds 的返回：合并后的阈值 + 是否使用默认。"""

    thresholds: Thresholds
    is_default: bool


def _load_stored_blob(db: Session) -> StoredBlob:
    raw = db.execute(
        text("SELECT value FROM app.meta WHERE key = :k"),
        {"k": META_KEY},
    ).scalar()
    if not raw:
        return StoredBlob(None, True)
    try:
        stored = json.loads(raw)
    except (TypeError, ValueError, json.JSONDecodeError):
        return StoredBlob(None, True)
    if not isinstance(stored, dict):
        return StoredBlob(None, True)
    return StoredBlob(stored, False)


def load_thresholds(db: Session) -> ThresholdsLoad:
    stored, is_default = _load_stored_blob(db)
    if is_default or stored is None:
        return ThresholdsLoad(DEFAULT_THRESHOLDS, True)
    return ThresholdsLoad(merge_thresholds(DEFAULT_THRESHOLDS, stored), False)


def _persist_thresholds(db: Session, t: Thresholds) -> None:
    db.execute(
        text(
            """
            INSERT INTO app.meta (key, value)
            VALUES (:k, :v)
            ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
            """
        ),
        {"k": META_KEY, "v": json.dumps(thresholds_to_dict(t), ensure_ascii=False)},
    )
    db.commit()


def save_thresholds(db: Session, patch: dict) -> Thresholds:
    current, _ = load_thresholds(db)
    effective = merge_thresholds(current, patch)
    _persist_thresholds(db, effective)
    cache_invalidate()
    return effective


def reset_thresholds(db: Session) -> Thresholds:
    db.execute(text("DELETE FROM app.meta WHERE key = :k"), {"k": META_KEY})
    db.commit()
    cache_invalidate()
    return DEFAULT_THRESHOLDS

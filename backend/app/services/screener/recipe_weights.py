"""选股多因子配方权重（可调 + app.meta 持久化）。"""

from __future__ import annotations

import json
import math
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.schemas.screener import RecipeWeightItem, RecipeWeightsOut

EDITABLE_RECIPES = frozenset({"intraday_multi", "post_close_multi", "ultra_short_unified"})

DEFAULT_WEIGHTS: dict[str, dict[str, float]] = {
    "intraday_multi": {
        "momentum": 0.35,
        "turnover": 0.25,
        "volume_ratio": 0.25,
        "surge": 0.15,
    },
    "post_close_multi": {
        "moneyflow": 0.40,
        "momentum": 0.30,
        "turnover": 0.20,
        "valuation": 0.10,
    },
    "ultra_short_unified": {
        "board": 0.40,
        "momentum": 0.35,
        "turnover": 0.25,
    },
}

FACTOR_LABELS: dict[str, dict[str, str]] = {
    "intraday_multi": {
        "momentum": "动量",
        "turnover": "换手",
        "volume_ratio": "量比",
        "surge": "成交额",
    },
    "post_close_multi": {
        "moneyflow": "资金",
        "momentum": "动量",
        "turnover": "换手",
        "valuation": "估值",
    },
    "ultra_short_unified": {
        "board": "连板",
        "momentum": "动量",
        "turnover": "换手",
    },
}


def meta_key(user_id: str) -> str:
    return f"screener/recipe_weights/{user_id}"


def normalize_weights(recipe_id: str, raw: dict) -> dict[str, float]:
    if recipe_id not in EDITABLE_RECIPES:
        raise ValueError(f"未知或不可编辑的配方：{recipe_id}")
    if not isinstance(raw, dict):
        raise ValueError("weights 必须是对象")
    factors = DEFAULT_WEIGHTS[recipe_id]
    known = set(factors.keys())
    values: dict[str, float] = {}
    for key, value in raw.items():
        if key not in known:
            raise ValueError(f"未知因子：{key}")
        try:
            weight = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"权重必须是数字：{key}") from exc
        if not math.isfinite(weight):
            raise ValueError(f"权重必须是有限数字：{key}")
        if weight < 0:
            raise ValueError(f"权重不能为负数：{key}")
        values[key] = weight
    total = sum(values.values())
    if total == 0:
        raise ValueError("权重之和不能为 0")
    # 按默认因子顺序归一，末项补偿使 round(4) 后和恰为 1.0
    ordered = [k for k in factors if k in values]
    out = {k: round(values[k] / total, 4) for k in ordered}
    if len(ordered) > 1:
        head = sum(out[k] for k in ordered[:-1])
        out[ordered[-1]] = round(1.0 - head, 4)
    return out


def _load_stored_blob(db: Session, user_id: str) -> dict[str, Any]:
    raw = db.execute(
        text("SELECT value FROM app.meta WHERE key = :k"),
        {"k": meta_key(user_id)},
    ).scalar()
    if not raw:
        return {}
    try:
        stored = json.loads(raw)
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    if not isinstance(stored, dict):
        return {}
    return stored


def _merge_recipe_weights(recipe_id: str, overrides: dict[str, float]) -> dict[str, float]:
    merged = dict(DEFAULT_WEIGHTS[recipe_id])
    merged.update(overrides)
    return normalize_weights(recipe_id, merged)


def load_recipe_weights(db: Session, user_id: str, recipe_id: str) -> dict[str, float]:
    if recipe_id not in EDITABLE_RECIPES:
        raise ValueError(f"未知或不可编辑的配方：{recipe_id}")
    stored = _load_stored_blob(db, user_id)
    recipe_blob = stored.get(recipe_id)
    if not isinstance(recipe_blob, dict):
        return dict(DEFAULT_WEIGHTS[recipe_id])
    factors = DEFAULT_WEIGHTS[recipe_id]
    overrides: dict[str, float] = {}
    for key, value in recipe_blob.items():
        if key not in factors:
            continue
        try:
            weight = float(value)
        except (TypeError, ValueError):
            continue
        if not math.isfinite(weight) or weight < 0:
            continue
        overrides[key] = weight
    if not overrides:
        return dict(DEFAULT_WEIGHTS[recipe_id])
    return _merge_recipe_weights(recipe_id, overrides)


def save_recipe_weights(
    db: Session,
    user_id: str,
    recipe_id: str,
    weights: dict,
) -> dict[str, float]:
    if recipe_id not in EDITABLE_RECIPES:
        raise ValueError(f"未知或不可编辑的配方：{recipe_id}")
    key = meta_key(user_id)
    if weights == {}:
        stored = _load_stored_blob(db, user_id)
        stored.pop(recipe_id, None)
        if not stored:
            db.execute(text("DELETE FROM app.meta WHERE key = :k"), {"k": key})
        else:
            db.execute(
                text(
                    """
                    INSERT INTO app.meta (key, value)
                    VALUES (:k, :v)
                    ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
                    """
                ),
                {"k": key, "v": json.dumps(stored, ensure_ascii=False)},
            )
        db.commit()
        return dict(DEFAULT_WEIGHTS[recipe_id])
    if not isinstance(weights, dict):
        raise ValueError("weights 必须是对象")
    factors = DEFAULT_WEIGHTS[recipe_id]
    known = set(factors.keys())
    overrides: dict[str, float] = {}
    for factor_key, value in weights.items():
        if factor_key not in known:
            raise ValueError(f"未知因子：{factor_key}")
        try:
            weight = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"权重必须是数字：{factor_key}") from exc
        if not math.isfinite(weight):
            raise ValueError(f"权重必须是有限数字：{factor_key}")
        if weight < 0:
            raise ValueError(f"权重不能为负数：{factor_key}")
        overrides[factor_key] = weight
    normalized = _merge_recipe_weights(recipe_id, overrides)
    stored = _load_stored_blob(db, user_id)
    stored[recipe_id] = normalized
    db.execute(
        text(
            """
            INSERT INTO app.meta (key, value)
            VALUES (:k, :v)
            ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
            """
        ),
        {"k": key, "v": json.dumps(stored, ensure_ascii=False)},
    )
    db.commit()
    return normalized


def weights_payload(recipe_id: str, merged: dict[str, float]) -> RecipeWeightsOut:
    if recipe_id not in EDITABLE_RECIPES:
        raise ValueError(f"未知或不可编辑的配方：{recipe_id}")
    factors = DEFAULT_WEIGHTS[recipe_id]
    labels = FACTOR_LABELS[recipe_id]
    items = [
        RecipeWeightItem(
            key=factor_key,
            label=labels[factor_key],
            weight=merged[factor_key],
            default_weight=factors[factor_key],
        )
        for factor_key in factors
    ]
    return RecipeWeightsOut(
        recipe_id=recipe_id,
        items=items,
        weights={factor_key: merged[factor_key] for factor_key in factors},
    )

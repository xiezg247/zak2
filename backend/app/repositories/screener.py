from __future__ import annotations

import csv
import io
import json
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.screener import ScreenerRecipe, ScreenerRun, ScreenerScheme
from app.repositories.pagination import Page, paginate
from app.schemas.screener import (
    RecipeCreate,
    RecipeUpdate,
    SchemeCreate,
    SchemeUpdate,
)


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def list_schemes(db: Session, user_id: str) -> list[ScreenerScheme]:
    return list(
        db.scalars(
            select(ScreenerScheme)
            .where(ScreenerScheme.user_id == user_id)
            .order_by(ScreenerScheme.updated_at.desc())
        )
    )


def create_scheme(db: Session, user_id: str, body: SchemeCreate) -> ScreenerScheme:
    now = _now()
    row = ScreenerScheme(
        id=str(uuid4()),
        user_id=user_id,
        name=body.name,
        config_json=json.dumps(body.config, ensure_ascii=False),
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def update_scheme(db: Session, user_id: str, scheme_id: str, body: SchemeUpdate) -> ScreenerScheme | None:
    row = db.scalar(
        select(ScreenerScheme).where(ScreenerScheme.id == scheme_id, ScreenerScheme.user_id == user_id)
    )
    if not row:
        return None
    if body.name is not None:
        row.name = body.name
    if body.config is not None:
        row.config_json = json.dumps(body.config, ensure_ascii=False)
    row.updated_at = _now()
    db.commit()
    db.refresh(row)
    return row


def delete_scheme(db: Session, user_id: str, scheme_id: str) -> bool:
    row = db.scalar(
        select(ScreenerScheme).where(ScreenerScheme.id == scheme_id, ScreenerScheme.user_id == user_id)
    )
    if not row:
        return False
    db.delete(row)
    db.commit()
    return True


def list_recipes(db: Session, user_id: str) -> list[ScreenerRecipe]:
    return list(
        db.scalars(
            select(ScreenerRecipe)
            .where(ScreenerRecipe.user_id == user_id)
            .order_by(ScreenerRecipe.updated_at.desc())
        )
    )


def create_recipe(db: Session, user_id: str, body: RecipeCreate) -> ScreenerRecipe:
    now = _now()
    row = ScreenerRecipe(
        id=str(uuid4()),
        user_id=user_id,
        name=body.name,
        trigger_kind=body.trigger_kind,
        config_json=json.dumps(body.config, ensure_ascii=False),
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def update_recipe(db: Session, user_id: str, recipe_id: str, body: RecipeUpdate) -> ScreenerRecipe | None:
    row = db.scalar(
        select(ScreenerRecipe).where(ScreenerRecipe.id == recipe_id, ScreenerRecipe.user_id == user_id)
    )
    if not row:
        return None
    if body.name is not None:
        row.name = body.name
    if body.trigger_kind is not None:
        row.trigger_kind = body.trigger_kind
    if body.config is not None:
        row.config_json = json.dumps(body.config, ensure_ascii=False)
    row.updated_at = _now()
    db.commit()
    db.refresh(row)
    return row


def delete_recipe(db: Session, user_id: str, recipe_id: str) -> bool:
    row = db.scalar(
        select(ScreenerRecipe).where(ScreenerRecipe.id == recipe_id, ScreenerRecipe.user_id == user_id)
    )
    if not row:
        return False
    db.delete(row)
    db.commit()
    return True


def save_run(
    db: Session,
    *,
    user_id: str,
    condition: str,
    source: str,
    result: dict[str, Any],
) -> ScreenerRun:
    row = ScreenerRun(
        id=str(uuid4()),
        user_id=user_id,
        condition=condition,
        source=source,
        row_count=int(result.get("row_count") or 0),
        total_scanned=int(result.get("total_scanned") or 0),
        config_json=json.dumps(result.get("config") or {}, ensure_ascii=False),
        result_json=json.dumps(result, ensure_ascii=False),
        created_at=_now(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def list_runs(db: Session, user_id: str, *, limit: int = 50) -> list[ScreenerRun]:
    return list(
        db.scalars(
            select(ScreenerRun)
            .where(ScreenerRun.user_id == user_id)
            .order_by(ScreenerRun.created_at.desc())
            .limit(limit)
        )
    )


def list_runs_page(db: Session, user_id: str, *, page: int = 1, page_size: int = 20) -> Page[ScreenerRun]:
    stmt = select(ScreenerRun).where(ScreenerRun.user_id == user_id).order_by(ScreenerRun.created_at.desc())
    return paginate(db, stmt, page=page, page_size=page_size)


def get_run(db: Session, user_id: str, run_id: str) -> ScreenerRun | None:
    return db.scalar(select(ScreenerRun).where(ScreenerRun.id == run_id, ScreenerRun.user_id == user_id))


def latest_run_symbols(db: Session, user_id: str) -> set[str] | None:
    row = db.scalar(
        select(ScreenerRun)
        .where(ScreenerRun.user_id == user_id)
        .order_by(ScreenerRun.created_at.desc())
        .limit(1)
    )
    if not row:
        return None
    try:
        data = json.loads(row.result_json)
    except json.JSONDecodeError:
        return None
    rows = data.get("rows") or []
    return {str(item.get("symbol")) for item in rows if item.get("symbol")}


def runs_to_csv(result: dict[str, Any]) -> str:
    rows = result.get("rows") or []
    buf = io.StringIO()
    fieldnames = [
        "symbol",
        "vt_symbol",
        "name",
        "last_price",
        "change_pct",
        "turnover_rate",
        "volume",
        "amount",
        "volume_ratio",
        "industry",
        "score",
    ]
    writer = csv.DictWriter(buf, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    for item in rows:
        writer.writerow(item)
    return buf.getvalue()

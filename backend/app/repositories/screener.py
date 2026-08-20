from __future__ import annotations

import csv
import io
import json
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import select

from app.models.screener import ScreenerRecipe, ScreenerRun, ScreenerScheme
from app.repositories.base import BaseRepository
from app.repositories.pagination import Page
from app.schemas.screener import (
    RecipeCreate,
    RecipeUpdate,
    SchemeCreate,
    SchemeUpdate,
)


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


class ScreenerSchemeRepository(BaseRepository[ScreenerScheme]):
    model = ScreenerScheme
    order_by = (ScreenerScheme.updated_at.desc(),)

    def list_schemes(self) -> list[ScreenerScheme]:
        return self.list_all()

    def create_scheme(self, body: SchemeCreate) -> ScreenerScheme:
        now = _now()
        return self.create(
            id=str(uuid4()),
            name=body.name,
            config_json=json.dumps(body.config, ensure_ascii=False),
            created_at=now,
            updated_at=now,
        )

    def update_scheme(self, scheme_id: str, body: SchemeUpdate) -> ScreenerScheme | None:
        row = self.get(scheme_id)
        if not row:
            return None
        if body.name is not None:
            row.name = body.name
        if body.config is not None:
            row.config_json = json.dumps(body.config, ensure_ascii=False)
        row.updated_at = _now()
        self.db.commit()
        self.db.refresh(row)
        return row

    def delete_scheme(self, scheme_id: str) -> bool:
        return self.delete(scheme_id)


class ScreenerRecipeRepository(BaseRepository[ScreenerRecipe]):
    model = ScreenerRecipe
    order_by = (ScreenerRecipe.updated_at.desc(),)

    def list_recipes(self) -> list[ScreenerRecipe]:
        return self.list_all()

    def create_recipe(self, body: RecipeCreate) -> ScreenerRecipe:
        now = _now()
        return self.create(
            id=str(uuid4()),
            name=body.name,
            trigger_kind=body.trigger_kind,
            config_json=json.dumps(body.config, ensure_ascii=False),
            created_at=now,
            updated_at=now,
        )

    def update_recipe(self, recipe_id: str, body: RecipeUpdate) -> ScreenerRecipe | None:
        row = self.get(recipe_id)
        if not row:
            return None
        if body.name is not None:
            row.name = body.name
        if body.trigger_kind is not None:
            row.trigger_kind = body.trigger_kind
        if body.config is not None:
            row.config_json = json.dumps(body.config, ensure_ascii=False)
        row.updated_at = _now()
        self.db.commit()
        self.db.refresh(row)
        return row

    def delete_recipe(self, recipe_id: str) -> bool:
        return self.delete(recipe_id)


class ScreenerRunRepository(BaseRepository[ScreenerRun]):
    model = ScreenerRun
    order_by = (ScreenerRun.created_at.desc(),)

    def save_run(
        self,
        *,
        condition: str,
        source: str,
        result: dict[str, Any],
    ) -> ScreenerRun:
        return self.create(
            id=str(uuid4()),
            condition=condition,
            source=source,
            row_count=int(result.get("row_count") or 0),
            total_scanned=int(result.get("total_scanned") or 0),
            config_json=json.dumps(result.get("config") or {}, ensure_ascii=False),
            result_json=json.dumps(result, ensure_ascii=False),
            created_at=_now(),
        )

    def list_runs(self, *, limit: int = 50) -> list[ScreenerRun]:
        return self.list_all(limit=limit)

    def list_runs_page(self, *, page: int = 1, page_size: int = 20) -> Page[ScreenerRun]:
        return self.paginate(page=page, page_size=page_size)

    def get_run(self, run_id: str) -> ScreenerRun | None:
        return self.get(run_id)

    def latest_run_symbols(self) -> set[str] | None:
        row = self.db.scalar(
            select(ScreenerRun)
            .where(ScreenerRun.user_id == self.user_id)
            .order_by(ScreenerRun.created_at.desc())
            .limit(1)
        )
        if not row:
            return None
        try:
            data = json.loads(row.result_json)
        except json.JSONDecodeError:
            return None
        # 兼容早期版本把「rows 列表」直接存入 result_json 的历史数据
        if isinstance(data, list):
            return {str(item.get("symbol")) for item in data if isinstance(item, dict) and item.get("symbol")}
        if not isinstance(data, dict):
            return None
        rows = data.get("rows") or []
        return {str(item.get("symbol")) for item in rows if isinstance(item, dict) and item.get("symbol")}


def runs_to_csv(result: dict[str, Any] | list[dict[str, Any]]) -> str:
    """把选股结果导出为 CSV 文本（纯函数，供 API 层调用）。

    兼容早期版本直接存 rows 列表的历史数据。
    """
    if isinstance(result, list):
        rows = result
    elif isinstance(result, dict):
        rows = result.get("rows") or []
    else:
        rows = []
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

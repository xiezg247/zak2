"""选股域编排：方案/配方 CRUD、权重、运行记录与入队。"""

from __future__ import annotations

import json

from sqlalchemy.orm import Session

from app.core.errors import NotFound, ValidationFailed
from app.core.settings import get_settings
from app.domains.screener import recipe_weights as recipe_weights_svc
from app.domains.screener.hard_filters import TEMPLATES
from app.domains.screener.pattern_screen import list_patterns as list_pattern_meta
from app.domains.screener.presets import (
    list_builtin_recipes as list_builtin_recipe_defs,
    list_presets as list_preset_defs,
)
from app.domains.screener.repository import (
    ScreenerRecipeRepository,
    ScreenerRunRepository,
    ScreenerSchemeRepository,
    runs_to_csv,
)
from app.domains.screener.schemas import (
    BuiltinRecipeOut,
    ConditionRunRequest,
    DataStatusOut,
    HardFilterTemplate,
    IndustryListOut,
    JobAccepted,
    PatternOut,
    PatternRunRequest,
    PresetOut,
    RecipeCreate,
    RecipeOut,
    RecipeRunRequest,
    RecipeUpdate,
    RecipeWeightsOut,
    RecipeWeightsPut,
    ReferencePeerRequest,
    RunDetail,
    RunSummary,
    SchemeCreate,
    SchemeOut,
    SchemeUpdate,
)
from app.schemas.common import PageOut
from app.services.market.quotes import get_quote_store
from app.services.market.stock_industry import list_industry_names
from app.services.ops.arq_jobs import SCREENER_FUNCS, enqueue_app_job


def _scheme_out(row) -> SchemeOut:  # type: ignore[no-untyped-def]
    return SchemeOut(
        id=row.id,
        name=row.name,
        config=json.loads(row.config_json or "{}"),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _recipe_out(row) -> RecipeOut:  # type: ignore[no-untyped-def]
    return RecipeOut(
        id=row.id,
        name=row.name,
        trigger_kind=row.trigger_kind,
        config=json.loads(row.config_json or "{}"),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _run_summary(row) -> RunSummary:  # type: ignore[no-untyped-def]
    return RunSummary(
        id=row.id,
        condition=row.condition,
        source=row.source,
        row_count=row.row_count,
        total_scanned=row.total_scanned,
        created_at=row.created_at,
    )


def _run_detail(row) -> RunDetail:  # type: ignore[no-untyped-def]
    result = json.loads(row.result_json or "{}")
    # 兼容早期版本直接存 rows 列表的历史数据，归一化为 dict 供前端读取
    if isinstance(result, list):
        result = {"rows": result, "row_count": len(result), "source": "legacy"}
    return RunDetail(
        id=row.id,
        condition=row.condition,
        source=row.source,
        row_count=row.row_count,
        total_scanned=row.total_scanned,
        created_at=row.created_at,
        config=json.loads(row.config_json or "{}"),
        result=result,
    )


class ScreenerService:
    @staticmethod
    def list_presets() -> list[PresetOut]:
        return list_preset_defs()

    @staticmethod
    def list_hard_filter_templates() -> list[HardFilterTemplate]:
        return TEMPLATES

    @staticmethod
    def list_industries(db: Session) -> IndustryListOut:
        return IndustryListOut(items=list_industry_names(db))

    @staticmethod
    def list_builtin_recipes() -> list[BuiltinRecipeOut]:
        return list_builtin_recipe_defs()

    @staticmethod
    def list_patterns() -> list[PatternOut]:
        return [PatternOut(**m) for m in list_pattern_meta()]

    @staticmethod
    def data_status() -> DataStatusOut:
        store = get_quote_store()
        meta = store.meta()
        return DataStatusOut(redis=meta, tushare_configured=bool(get_settings().tushare_token))

    @staticmethod
    def list_schemes(db: Session, user_id: str) -> list[SchemeOut]:
        return [_scheme_out(r) for r in ScreenerSchemeRepository(db, user_id).list_schemes()]

    @staticmethod
    def create_scheme(db: Session, user_id: str, body: SchemeCreate) -> SchemeOut:
        return _scheme_out(ScreenerSchemeRepository(db, user_id).create_scheme(body))

    @staticmethod
    def update_scheme(db: Session, user_id: str, scheme_id: str, body: SchemeUpdate) -> SchemeOut:
        row = ScreenerSchemeRepository(db, user_id).update_scheme(scheme_id, body)
        if not row:
            raise NotFound("方案不存在")
        return _scheme_out(row)

    @staticmethod
    def delete_scheme(db: Session, user_id: str, scheme_id: str) -> None:
        if not ScreenerSchemeRepository(db, user_id).delete_scheme(scheme_id):
            raise NotFound("方案不存在")

    @staticmethod
    def list_recipes(db: Session, user_id: str) -> list[RecipeOut]:
        return [_recipe_out(r) for r in ScreenerRecipeRepository(db, user_id).list_recipes()]

    @staticmethod
    def create_recipe(db: Session, user_id: str, body: RecipeCreate) -> RecipeOut:
        return _recipe_out(ScreenerRecipeRepository(db, user_id).create_recipe(body))

    @staticmethod
    def update_recipe(db: Session, user_id: str, recipe_id: str, body: RecipeUpdate) -> RecipeOut:
        row = ScreenerRecipeRepository(db, user_id).update_recipe(recipe_id, body)
        if not row:
            raise NotFound("配方不存在")
        return _recipe_out(row)

    @staticmethod
    def delete_recipe(db: Session, user_id: str, recipe_id: str) -> None:
        if not ScreenerRecipeRepository(db, user_id).delete_recipe(recipe_id):
            raise NotFound("配方不存在")

    @staticmethod
    def get_recipe_weights(db: Session, user_id: str, recipe_id: str) -> RecipeWeightsOut:
        if recipe_id not in recipe_weights_svc.EDITABLE_RECIPES:
            raise ValidationFailed(f"未知或不可编辑的配方：{recipe_id}")
        merged = recipe_weights_svc.load_recipe_weights(db, user_id, recipe_id)
        return recipe_weights_svc.weights_payload(recipe_id, merged)

    @staticmethod
    def put_recipe_weights(
        db: Session, user_id: str, recipe_id: str, body: RecipeWeightsPut
    ) -> RecipeWeightsOut:
        if recipe_id not in recipe_weights_svc.EDITABLE_RECIPES:
            raise ValidationFailed(f"未知或不可编辑的配方：{recipe_id}")
        try:
            merged = recipe_weights_svc.save_recipe_weights(
                db, user_id, recipe_id, dict(body.weights or {})
            )
        except ValueError as exc:
            raise ValidationFailed(str(exc)) from exc
        return recipe_weights_svc.weights_payload(recipe_id, merged)

    @staticmethod
    async def enqueue_condition_run(user_id: str, body: ConditionRunRequest) -> JobAccepted:
        kind = "screener.condition"
        job_id = await enqueue_app_job(
            function=SCREENER_FUNCS[kind],
            kind=kind,
            user_id=user_id,
            payload=body.model_dump(),
        )
        return JobAccepted(job_id=job_id)

    @staticmethod
    async def enqueue_recipe_run(user_id: str, body: RecipeRunRequest) -> JobAccepted:
        kind = "screener.recipe"
        job_id = await enqueue_app_job(
            function=SCREENER_FUNCS[kind],
            kind=kind,
            user_id=user_id,
            payload=body.model_dump(),
        )
        return JobAccepted(job_id=job_id)

    @staticmethod
    async def enqueue_pattern_run(user_id: str, body: PatternRunRequest) -> JobAccepted:
        kind = "screener.pattern"
        job_id = await enqueue_app_job(
            function=SCREENER_FUNCS[kind],
            kind=kind,
            user_id=user_id,
            payload=body.model_dump(),
        )
        return JobAccepted(job_id=job_id)

    @staticmethod
    async def enqueue_reference_peer_run(user_id: str, body: ReferencePeerRequest) -> JobAccepted:
        kind = "screener.reference_peer"
        job_id = await enqueue_app_job(
            function=SCREENER_FUNCS[kind],
            kind=kind,
            user_id=user_id,
            payload=body.model_dump(),
        )
        return JobAccepted(job_id=job_id)

    @staticmethod
    def list_runs(db: Session, user_id: str) -> list[RunSummary]:
        return [_run_summary(r) for r in ScreenerRunRepository(db, user_id).list_runs()]

    @staticmethod
    def list_runs_page(db: Session, user_id: str, *, page: int, page_size: int) -> PageOut[RunSummary]:
        result = ScreenerRunRepository(db, user_id).list_runs_page(page=page, page_size=page_size)
        return PageOut.from_page(result.map(_run_summary))

    @staticmethod
    def get_run(db: Session, user_id: str, run_id: str) -> RunDetail:
        row = ScreenerRunRepository(db, user_id).get_run(run_id)
        if not row:
            raise NotFound("运行记录不存在")
        return _run_detail(row)

    @staticmethod
    def export_run_csv(db: Session, user_id: str, run_id: str) -> str:
        row = ScreenerRunRepository(db, user_id).get_run(run_id)
        if not row:
            raise NotFound("运行记录不存在")
        result = json.loads(row.result_json or "{}")
        return runs_to_csv(result)

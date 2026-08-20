from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.db import get_db
from app.models.user import User
from app.repositories import screener as repo
from app.schemas.common import ApiResponse, OkOut, PageOut
from app.schemas.screener import (
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
from app.services.market.quotes import get_quote_store
from app.services.market.stock_industry import list_industry_names
from app.services.ops.arq_jobs import SCREENER_FUNCS, enqueue_app_job
from app.services.screener import recipe_weights as recipe_weights_svc
from app.services.screener.hard_filters import TEMPLATES
from app.services.screener.pattern_screen import list_patterns
from app.services.screener.presets import list_builtin_recipes, list_presets

router = APIRouter(prefix="/screener", tags=["screener"])


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


@router.get("/presets", response_model=ApiResponse[list[PresetOut]])
def presets(user: User = Depends(get_current_user)) -> ApiResponse[list[PresetOut]]:
    _ = user
    return ApiResponse(data=list_presets())


@router.get("/hard-filter-templates", response_model=ApiResponse[list[HardFilterTemplate]])
def hard_filter_templates(user: User = Depends(get_current_user)) -> ApiResponse[list[HardFilterTemplate]]:
    _ = user
    return ApiResponse(data=TEMPLATES)


@router.get("/industries", response_model=ApiResponse[IndustryListOut])
def industries(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[IndustryListOut]:
    _ = user
    return ApiResponse(data=IndustryListOut(items=list_industry_names(db)))


@router.get("/builtin-recipes", response_model=ApiResponse[list[BuiltinRecipeOut]])
def builtin_recipes(user: User = Depends(get_current_user)) -> ApiResponse[list[BuiltinRecipeOut]]:
    _ = user
    return ApiResponse(data=list_builtin_recipes())


@router.get("/patterns", response_model=ApiResponse[list[PatternOut]])
def patterns(user: User = Depends(get_current_user)) -> ApiResponse[list[PatternOut]]:
    _ = user
    return ApiResponse(data=[PatternOut(**m) for m in list_patterns()])


@router.get("/data-status", response_model=ApiResponse[DataStatusOut])
def data_status(user: User = Depends(get_current_user)) -> ApiResponse[DataStatusOut]:
    _ = user
    from app.core.settings import get_settings

    store = get_quote_store()
    meta = store.meta()
    return ApiResponse(data=DataStatusOut(redis=meta, tushare_configured=bool(get_settings().tushare_token)))


@router.get("/schemes", response_model=ApiResponse[list[SchemeOut]])
def get_schemes(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> ApiResponse[list[SchemeOut]]:
    return ApiResponse(data=[_scheme_out(r) for r in repo.ScreenerSchemeRepository(db, str(user.id)).list_schemes()])


@router.post("/schemes", response_model=ApiResponse[SchemeOut])
def post_scheme(
    body: SchemeCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[SchemeOut]:
    return ApiResponse(data=_scheme_out(repo.ScreenerSchemeRepository(db, str(user.id)).create_scheme(body)))


@router.patch("/schemes/{scheme_id}", response_model=ApiResponse[SchemeOut])
def patch_scheme(
    scheme_id: str,
    body: SchemeUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[SchemeOut]:
    row = repo.ScreenerSchemeRepository(db, str(user.id)).update_scheme(scheme_id, body)
    if not row:
        raise HTTPException(status_code=404, detail="方案不存在")
    return ApiResponse(data=_scheme_out(row))


@router.delete("/schemes/{scheme_id}", response_model=ApiResponse[OkOut])
def remove_scheme(
    scheme_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[OkOut]:
    if not repo.ScreenerSchemeRepository(db, str(user.id)).delete_scheme(scheme_id):
        raise HTTPException(status_code=404, detail="方案不存在")
    return ApiResponse(data=OkOut())


@router.get("/recipes", response_model=ApiResponse[list[RecipeOut]])
def get_recipes(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> ApiResponse[list[RecipeOut]]:
    return ApiResponse(data=[_recipe_out(r) for r in repo.ScreenerRecipeRepository(db, str(user.id)).list_recipes()])


@router.post("/recipes", response_model=ApiResponse[RecipeOut])
def post_recipe(
    body: RecipeCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[RecipeOut]:
    return ApiResponse(data=_recipe_out(repo.ScreenerRecipeRepository(db, str(user.id)).create_recipe(body)))


@router.patch("/recipes/{recipe_id}", response_model=ApiResponse[RecipeOut])
def patch_recipe(
    recipe_id: str,
    body: RecipeUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[RecipeOut]:
    row = repo.ScreenerRecipeRepository(db, str(user.id)).update_recipe(recipe_id, body)
    if not row:
        raise HTTPException(status_code=404, detail="配方不存在")
    return ApiResponse(data=_recipe_out(row))


@router.delete("/recipes/{recipe_id}", response_model=ApiResponse[OkOut])
def remove_recipe(
    recipe_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[OkOut]:
    if not repo.ScreenerRecipeRepository(db, str(user.id)).delete_recipe(recipe_id):
        raise HTTPException(status_code=404, detail="配方不存在")
    return ApiResponse(data=OkOut())


@router.get("/recipes/{recipe_id}/weights", response_model=ApiResponse[RecipeWeightsOut])
def get_recipe_weights(
    recipe_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[RecipeWeightsOut]:
    if recipe_id not in recipe_weights_svc.EDITABLE_RECIPES:
        raise HTTPException(status_code=400, detail=f"未知或不可编辑的配方：{recipe_id}")
    merged = recipe_weights_svc.load_recipe_weights(db, str(user.id), recipe_id)
    return ApiResponse(data=recipe_weights_svc.weights_payload(recipe_id, merged))


@router.put("/recipes/{recipe_id}/weights", response_model=ApiResponse[RecipeWeightsOut])
def put_recipe_weights(
    recipe_id: str,
    body: RecipeWeightsPut,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[RecipeWeightsOut]:
    if recipe_id not in recipe_weights_svc.EDITABLE_RECIPES:
        raise HTTPException(status_code=400, detail=f"未知或不可编辑的配方：{recipe_id}")
    try:
        merged = recipe_weights_svc.save_recipe_weights(db, str(user.id), recipe_id, dict(body.weights or {}))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ApiResponse(data=recipe_weights_svc.weights_payload(recipe_id, merged))


@router.post("/runs/condition", response_model=ApiResponse[JobAccepted])
async def post_condition_run(
    body: ConditionRunRequest,
    user: User = Depends(get_current_user),
) -> ApiResponse[JobAccepted]:
    kind = "screener.condition"
    job_id = await enqueue_app_job(
        function=SCREENER_FUNCS[kind],
        kind=kind,
        user_id=str(user.id),
        payload=body.model_dump(),
    )
    return ApiResponse(data=JobAccepted(job_id=job_id))


@router.post("/runs/recipe", response_model=ApiResponse[JobAccepted])
async def post_recipe_run(
    body: RecipeRunRequest,
    user: User = Depends(get_current_user),
) -> ApiResponse[JobAccepted]:
    kind = "screener.recipe"
    job_id = await enqueue_app_job(
        function=SCREENER_FUNCS[kind],
        kind=kind,
        user_id=str(user.id),
        payload=body.model_dump(),
    )
    return ApiResponse(data=JobAccepted(job_id=job_id))


@router.post("/runs/pattern", response_model=ApiResponse[JobAccepted])
async def post_pattern_run(
    body: PatternRunRequest,
    user: User = Depends(get_current_user),
) -> ApiResponse[JobAccepted]:
    kind = "screener.pattern"
    job_id = await enqueue_app_job(
        function=SCREENER_FUNCS[kind],
        kind=kind,
        user_id=str(user.id),
        payload=body.model_dump(),
    )
    return ApiResponse(data=JobAccepted(job_id=job_id))


@router.post("/runs/reference-peer", response_model=ApiResponse[JobAccepted])
async def post_reference_peer_run(
    body: ReferencePeerRequest,
    user: User = Depends(get_current_user),
) -> ApiResponse[JobAccepted]:
    kind = "screener.reference_peer"
    job_id = await enqueue_app_job(
        function=SCREENER_FUNCS[kind],
        kind=kind,
        user_id=str(user.id),
        payload=body.model_dump(),
    )
    return ApiResponse(data=JobAccepted(job_id=job_id))


@router.get("/runs", response_model=ApiResponse[list[RunSummary]])
def get_runs(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> ApiResponse[list[RunSummary]]:
    return ApiResponse(data=[_run_summary(r) for r in repo.ScreenerRunRepository(db, str(user.id)).list_runs()])


@router.get("/runs/page", response_model=ApiResponse[PageOut[RunSummary]])
def get_runs_page(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[PageOut[RunSummary]]:
    result = repo.ScreenerRunRepository(db, str(user.id)).list_runs_page(page=page, page_size=page_size)
    return ApiResponse(data=PageOut.from_page(result.map(_run_summary)))


@router.get("/runs/{run_id}", response_model=ApiResponse[RunDetail])
def get_run_detail(
    run_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[RunDetail]:
    row = repo.ScreenerRunRepository(db, str(user.id)).get_run(run_id)
    if not row:
        raise HTTPException(status_code=404, detail="运行记录不存在")
    return ApiResponse(data=_run_detail(row))


@router.get("/runs/{run_id}/export.csv")
def export_run_csv(
    run_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    row = repo.ScreenerRunRepository(db, str(user.id)).get_run(run_id)
    if not row:
        raise HTTPException(status_code=404, detail="运行记录不存在")
    result = json.loads(row.result_json or "{}")
    csv_text = repo.runs_to_csv(result)
    return Response(
        content=csv_text,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="screener_{run_id}.csv"'},
    )

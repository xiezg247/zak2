from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.db import get_db
from app.models.user import User
from app.schemas.screener import (
    BuiltinRecipeOut,
    ConditionRunRequest,
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
from app.services import recipe_weights as recipe_weights_svc
from app.services import screener_repo as repo
from app.services.arq_jobs import SCREENER_FUNCS, enqueue_app_job
from app.services.hard_filters import TEMPLATES
from app.services.pattern_screen import list_patterns
from app.services.presets import list_builtin_recipes, list_presets
from app.services.quotes import get_quote_store
from app.services.stock_industry import list_industry_names

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


@router.get("/presets", response_model=list[PresetOut])
def presets(user: User = Depends(get_current_user)) -> list[PresetOut]:
    _ = user
    return list_presets()


@router.get("/hard-filter-templates", response_model=list[HardFilterTemplate])
def hard_filter_templates(user: User = Depends(get_current_user)) -> list[HardFilterTemplate]:
    _ = user
    return TEMPLATES


@router.get("/industries", response_model=IndustryListOut)
def industries(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> IndustryListOut:
    _ = user
    return IndustryListOut(items=list_industry_names(db))


@router.get("/builtin-recipes", response_model=list[BuiltinRecipeOut])
def builtin_recipes(user: User = Depends(get_current_user)) -> list[BuiltinRecipeOut]:
    _ = user
    return list_builtin_recipes()


@router.get("/patterns", response_model=list[PatternOut])
def patterns(user: User = Depends(get_current_user)) -> list[PatternOut]:
    _ = user
    return [PatternOut(**m) for m in list_patterns()]


@router.get("/data-status")
def data_status(user: User = Depends(get_current_user)) -> dict:
    _ = user
    from app.core.settings import get_settings

    store = get_quote_store()
    meta = store.meta()
    return {"redis": meta, "tushare_configured": bool(get_settings().tushare_token)}


@router.get("/schemes", response_model=list[SchemeOut])
def get_schemes(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[SchemeOut]:
    return [_scheme_out(r) for r in repo.list_schemes(db, str(user.id))]


@router.post("/schemes", response_model=SchemeOut)
def post_scheme(
    body: SchemeCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SchemeOut:
    return _scheme_out(repo.create_scheme(db, str(user.id), body))


@router.patch("/schemes/{scheme_id}", response_model=SchemeOut)
def patch_scheme(
    scheme_id: str,
    body: SchemeUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SchemeOut:
    row = repo.update_scheme(db, str(user.id), scheme_id, body)
    if not row:
        raise HTTPException(status_code=404, detail="方案不存在")
    return _scheme_out(row)


@router.delete("/schemes/{scheme_id}")
def remove_scheme(
    scheme_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    if not repo.delete_scheme(db, str(user.id), scheme_id):
        raise HTTPException(status_code=404, detail="方案不存在")
    return {"ok": True}


@router.get("/recipes", response_model=list[RecipeOut])
def get_recipes(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[RecipeOut]:
    return [_recipe_out(r) for r in repo.list_recipes(db, str(user.id))]


@router.post("/recipes", response_model=RecipeOut)
def post_recipe(
    body: RecipeCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RecipeOut:
    return _recipe_out(repo.create_recipe(db, str(user.id), body))


@router.patch("/recipes/{recipe_id}", response_model=RecipeOut)
def patch_recipe(
    recipe_id: str,
    body: RecipeUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RecipeOut:
    row = repo.update_recipe(db, str(user.id), recipe_id, body)
    if not row:
        raise HTTPException(status_code=404, detail="配方不存在")
    return _recipe_out(row)


@router.delete("/recipes/{recipe_id}")
def remove_recipe(
    recipe_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    if not repo.delete_recipe(db, str(user.id), recipe_id):
        raise HTTPException(status_code=404, detail="配方不存在")
    return {"ok": True}


@router.get("/recipes/{recipe_id}/weights", response_model=RecipeWeightsOut)
def get_recipe_weights(
    recipe_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RecipeWeightsOut:
    if recipe_id not in recipe_weights_svc.EDITABLE_RECIPES:
        raise HTTPException(status_code=400, detail=f"未知或不可编辑的配方：{recipe_id}")
    merged = recipe_weights_svc.load_recipe_weights(db, str(user.id), recipe_id)
    return RecipeWeightsOut(**recipe_weights_svc.weights_payload(recipe_id, merged))


@router.put("/recipes/{recipe_id}/weights", response_model=RecipeWeightsOut)
def put_recipe_weights(
    recipe_id: str,
    body: RecipeWeightsPut,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RecipeWeightsOut:
    if recipe_id not in recipe_weights_svc.EDITABLE_RECIPES:
        raise HTTPException(status_code=400, detail=f"未知或不可编辑的配方：{recipe_id}")
    try:
        merged = recipe_weights_svc.save_recipe_weights(
            db, str(user.id), recipe_id, dict(body.weights or {})
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RecipeWeightsOut(**recipe_weights_svc.weights_payload(recipe_id, merged))


@router.post("/runs/condition", response_model=JobAccepted)
async def post_condition_run(
    body: ConditionRunRequest,
    user: User = Depends(get_current_user),
) -> JobAccepted:
    kind = "screener.condition"
    job_id = await enqueue_app_job(
        function=SCREENER_FUNCS[kind],
        kind=kind,
        user_id=str(user.id),
        payload=body.model_dump(),
    )
    return JobAccepted(job_id=job_id)


@router.post("/runs/recipe", response_model=JobAccepted)
async def post_recipe_run(
    body: RecipeRunRequest,
    user: User = Depends(get_current_user),
) -> JobAccepted:
    kind = "screener.recipe"
    job_id = await enqueue_app_job(
        function=SCREENER_FUNCS[kind],
        kind=kind,
        user_id=str(user.id),
        payload=body.model_dump(),
    )
    return JobAccepted(job_id=job_id)


@router.post("/runs/pattern", response_model=JobAccepted)
async def post_pattern_run(
    body: PatternRunRequest,
    user: User = Depends(get_current_user),
) -> JobAccepted:
    kind = "screener.pattern"
    job_id = await enqueue_app_job(
        function=SCREENER_FUNCS[kind],
        kind=kind,
        user_id=str(user.id),
        payload=body.model_dump(),
    )
    return JobAccepted(job_id=job_id)


@router.post("/runs/reference-peer", response_model=JobAccepted)
async def post_reference_peer_run(
    body: ReferencePeerRequest,
    user: User = Depends(get_current_user),
) -> JobAccepted:
    kind = "screener.reference_peer"
    job_id = await enqueue_app_job(
        function=SCREENER_FUNCS[kind],
        kind=kind,
        user_id=str(user.id),
        payload=body.model_dump(),
    )
    return JobAccepted(job_id=job_id)


@router.get("/runs", response_model=list[RunSummary])
def get_runs(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[RunSummary]:
    return [_run_summary(r) for r in repo.list_runs(db, str(user.id))]


@router.get("/runs/{run_id}", response_model=RunDetail)
def get_run_detail(
    run_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RunDetail:
    row = repo.get_run(db, str(user.id), run_id)
    if not row:
        raise HTTPException(status_code=404, detail="运行记录不存在")
    return _run_detail(row)


@router.get("/runs/{run_id}/export.csv")
def export_run_csv(
    run_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    row = repo.get_run(db, str(user.id), run_id)
    if not row:
        raise HTTPException(status_code=404, detail="运行记录不存在")
    result = json.loads(row.result_json or "{}")
    csv_text = repo.runs_to_csv(result)
    return Response(
        content=csv_text,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="screener_{run_id}.csv"'},
    )

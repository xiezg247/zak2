"""选股薄路由：Depends + ScreenerService。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.db import get_db
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
from app.domains.screener.service import ScreenerService
from app.models.user import User
from app.schemas.common import ApiResponse, OkOut, PageOut

router = APIRouter(prefix="/screener", tags=["screener"])


@router.get("/presets", response_model=ApiResponse[list[PresetOut]])
def presets(user: User = Depends(get_current_user)) -> ApiResponse[list[PresetOut]]:
    _ = user
    return ApiResponse(data=ScreenerService.list_presets())


@router.get("/hard-filter-templates", response_model=ApiResponse[list[HardFilterTemplate]])
def hard_filter_templates(user: User = Depends(get_current_user)) -> ApiResponse[list[HardFilterTemplate]]:
    _ = user
    return ApiResponse(data=ScreenerService.list_hard_filter_templates())


@router.get("/industries", response_model=ApiResponse[IndustryListOut])
def industries(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[IndustryListOut]:
    _ = user
    return ApiResponse(data=ScreenerService.list_industries(db))


@router.get("/builtin-recipes", response_model=ApiResponse[list[BuiltinRecipeOut]])
def builtin_recipes(user: User = Depends(get_current_user)) -> ApiResponse[list[BuiltinRecipeOut]]:
    _ = user
    return ApiResponse(data=ScreenerService.list_builtin_recipes())


@router.get("/patterns", response_model=ApiResponse[list[PatternOut]])
def patterns(user: User = Depends(get_current_user)) -> ApiResponse[list[PatternOut]]:
    _ = user
    return ApiResponse(data=ScreenerService.list_patterns())


@router.get("/data-status", response_model=ApiResponse[DataStatusOut])
def data_status(user: User = Depends(get_current_user)) -> ApiResponse[DataStatusOut]:
    _ = user
    return ApiResponse(data=ScreenerService.data_status())


@router.get("/schemes", response_model=ApiResponse[list[SchemeOut]])
def get_schemes(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> ApiResponse[list[SchemeOut]]:
    return ApiResponse(data=ScreenerService.list_schemes(db, str(user.id)))


@router.post("/schemes", response_model=ApiResponse[SchemeOut])
def post_scheme(
    body: SchemeCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[SchemeOut]:
    return ApiResponse(data=ScreenerService.create_scheme(db, str(user.id), body))


@router.patch("/schemes/{scheme_id}", response_model=ApiResponse[SchemeOut])
def patch_scheme(
    scheme_id: str,
    body: SchemeUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[SchemeOut]:
    return ApiResponse(data=ScreenerService.update_scheme(db, str(user.id), scheme_id, body))


@router.delete("/schemes/{scheme_id}", response_model=ApiResponse[OkOut])
def remove_scheme(
    scheme_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[OkOut]:
    ScreenerService.delete_scheme(db, str(user.id), scheme_id)
    return ApiResponse(data=OkOut())


@router.get("/recipes", response_model=ApiResponse[list[RecipeOut]])
def get_recipes(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> ApiResponse[list[RecipeOut]]:
    return ApiResponse(data=ScreenerService.list_recipes(db, str(user.id)))


@router.post("/recipes", response_model=ApiResponse[RecipeOut])
def post_recipe(
    body: RecipeCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[RecipeOut]:
    return ApiResponse(data=ScreenerService.create_recipe(db, str(user.id), body))


@router.patch("/recipes/{recipe_id}", response_model=ApiResponse[RecipeOut])
def patch_recipe(
    recipe_id: str,
    body: RecipeUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[RecipeOut]:
    return ApiResponse(data=ScreenerService.update_recipe(db, str(user.id), recipe_id, body))


@router.delete("/recipes/{recipe_id}", response_model=ApiResponse[OkOut])
def remove_recipe(
    recipe_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[OkOut]:
    ScreenerService.delete_recipe(db, str(user.id), recipe_id)
    return ApiResponse(data=OkOut())


@router.get("/recipes/{recipe_id}/weights", response_model=ApiResponse[RecipeWeightsOut])
def get_recipe_weights(
    recipe_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[RecipeWeightsOut]:
    return ApiResponse(data=ScreenerService.get_recipe_weights(db, str(user.id), recipe_id))


@router.put("/recipes/{recipe_id}/weights", response_model=ApiResponse[RecipeWeightsOut])
def put_recipe_weights(
    recipe_id: str,
    body: RecipeWeightsPut,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[RecipeWeightsOut]:
    return ApiResponse(data=ScreenerService.put_recipe_weights(db, str(user.id), recipe_id, body))


@router.post("/runs/condition", response_model=ApiResponse[JobAccepted])
async def post_condition_run(
    body: ConditionRunRequest,
    user: User = Depends(get_current_user),
) -> ApiResponse[JobAccepted]:
    return ApiResponse(data=await ScreenerService.enqueue_condition_run(str(user.id), body))


@router.post("/runs/recipe", response_model=ApiResponse[JobAccepted])
async def post_recipe_run(
    body: RecipeRunRequest,
    user: User = Depends(get_current_user),
) -> ApiResponse[JobAccepted]:
    return ApiResponse(data=await ScreenerService.enqueue_recipe_run(str(user.id), body))


@router.post("/runs/pattern", response_model=ApiResponse[JobAccepted])
async def post_pattern_run(
    body: PatternRunRequest,
    user: User = Depends(get_current_user),
) -> ApiResponse[JobAccepted]:
    return ApiResponse(data=await ScreenerService.enqueue_pattern_run(str(user.id), body))


@router.post("/runs/reference-peer", response_model=ApiResponse[JobAccepted])
async def post_reference_peer_run(
    body: ReferencePeerRequest,
    user: User = Depends(get_current_user),
) -> ApiResponse[JobAccepted]:
    return ApiResponse(data=await ScreenerService.enqueue_reference_peer_run(str(user.id), body))


@router.get("/runs", response_model=ApiResponse[list[RunSummary]])
def get_runs(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> ApiResponse[list[RunSummary]]:
    return ApiResponse(data=ScreenerService.list_runs(db, str(user.id)))


@router.get("/runs/page", response_model=ApiResponse[PageOut[RunSummary]])
def get_runs_page(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[PageOut[RunSummary]]:
    return ApiResponse(data=ScreenerService.list_runs_page(db, str(user.id), page=page, page_size=page_size))


@router.get("/runs/{run_id}", response_model=ApiResponse[RunDetail])
def get_run_detail(
    run_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[RunDetail]:
    return ApiResponse(data=ScreenerService.get_run(db, str(user.id), run_id))


@router.get("/runs/{run_id}/export.csv")
def export_run_csv(
    run_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    csv_text = ScreenerService.export_run_csv(db, str(user.id), run_id)
    return Response(
        content=csv_text,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="screener_{run_id}.csv"'},
    )

"""回测薄路由：Depends + BacktestService。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.db import get_db
from app.domains.backtest.schemas import (
    BacktestBatchOut,
    BacktestRunOut,
    BacktestRunRequest,
    BatchBacktestRequest,
    JobAccepted,
    OptimizeBacktestRequest,
    OptimizeSummaryOut,
    StrategyInfo,
    StrategyProfileOut,
)
from app.domains.backtest.service import BacktestService
from app.models.user import User
from app.schemas.common import ApiResponse, PageOut

router = APIRouter(prefix="/backtest", tags=["backtest"])


@router.get("/strategies", response_model=ApiResponse[list[StrategyInfo]])
def list_strategies(user: User = Depends(get_current_user)) -> ApiResponse[list[StrategyInfo]]:
    _ = user
    return ApiResponse(data=BacktestService.list_strategies())


@router.get("/profiles", response_model=ApiResponse[list[StrategyProfileOut]])
def list_profiles(user: User = Depends(get_current_user)) -> ApiResponse[list[StrategyProfileOut]]:
    _ = user
    return ApiResponse(data=BacktestService.list_profiles())


@router.get("/runs", response_model=ApiResponse[list[BacktestRunOut]])
def get_runs(
    limit: int = Query(default=50, ge=1, le=200),
    batch_id: str | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[list[BacktestRunOut]]:
    return ApiResponse(data=BacktestService.list_runs(db, str(user.id), limit=limit, batch_id=batch_id))


@router.get("/runs/page", response_model=ApiResponse[PageOut[BacktestRunOut]])
def get_runs_page(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    batch_id: str | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[PageOut[BacktestRunOut]]:
    return ApiResponse(
        data=BacktestService.list_runs_page(
            db, str(user.id), page=page, page_size=page_size, batch_id=batch_id
        )
    )


@router.get("/runs/{run_id}", response_model=ApiResponse[BacktestRunOut])
def get_run(
    run_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[BacktestRunOut]:
    return ApiResponse(data=BacktestService.get_run(db, str(user.id), run_id))


@router.get("/batches", response_model=ApiResponse[list[BacktestBatchOut]])
def get_batches(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> ApiResponse[list[BacktestBatchOut]]:
    return ApiResponse(data=BacktestService.list_batches(db, str(user.id)))


@router.post("/runs", response_model=ApiResponse[JobAccepted])
async def post_run(body: BacktestRunRequest, user: User = Depends(get_current_user)) -> ApiResponse[JobAccepted]:
    return ApiResponse(data=await BacktestService.enqueue_single(str(user.id), body))


@router.post("/runs/batch", response_model=ApiResponse[JobAccepted])
async def post_batch(body: BatchBacktestRequest, user: User = Depends(get_current_user)) -> ApiResponse[JobAccepted]:
    return ApiResponse(data=await BacktestService.enqueue_batch(str(user.id), body))


@router.post("/optimize", response_model=ApiResponse[JobAccepted])
async def post_optimize(
    body: OptimizeBacktestRequest, user: User = Depends(get_current_user)
) -> ApiResponse[JobAccepted]:
    return ApiResponse(data=await BacktestService.enqueue_optimize(str(user.id), body))


@router.get("/optimize/{batch_id}", response_model=ApiResponse[OptimizeSummaryOut])
def get_optimize(
    batch_id: str,
    objective: str = Query(default="sharpe_ratio"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[OptimizeSummaryOut]:
    return ApiResponse(
        data=BacktestService.summarize_optimize(db, str(user.id), batch_id, objective=objective)
    )

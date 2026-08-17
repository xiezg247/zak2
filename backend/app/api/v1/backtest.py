from __future__ import annotations

from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.db import get_db
from app.models.user import User
from app.schemas.backtest import (
    BatchBacktestRequest,
    BacktestRunOut,
    BacktestRunRequest,
    JobAccepted,
    OptimizeBacktestRequest,
    OptimizeSummaryOut,
    StrategyInfo,
    StrategyProfileOut,
)
from app.schemas.common import ApiResponse, PageOut
from app.repositories import backtest as repo
from app.services.arq_jobs import BACKTEST_FUNCS, enqueue_app_job
from app.services.backtest_engine import PROFILES, STRATEGIES
from app.services.backtest_optimize import expand_ma_grid

router = APIRouter(prefix="/backtest", tags=["backtest"])


def _validate_ma_windows(fast: int, slow: int) -> None:
    if fast >= slow:
        raise HTTPException(status_code=400, detail="fast_window 须小于 slow_window")


@router.get("/strategies", response_model=ApiResponse[list[StrategyInfo]])
def list_strategies(user: User = Depends(get_current_user)) -> ApiResponse[list[StrategyInfo]]:
    _ = user
    return ApiResponse(data=[StrategyInfo(**s) for s in STRATEGIES])


@router.get("/profiles", response_model=ApiResponse[list[StrategyProfileOut]])
def list_profiles(user: User = Depends(get_current_user)) -> ApiResponse[list[StrategyProfileOut]]:
    _ = user
    return ApiResponse(data=[StrategyProfileOut(**p) for p in PROFILES])


@router.get("/runs", response_model=ApiResponse[list[BacktestRunOut]])
def get_runs(
    limit: int = Query(default=50, ge=1, le=200),
    batch_id: str | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[list[BacktestRunOut]]:
    return ApiResponse(data=repo.BacktestRepository(db, str(user.id)).list_runs(limit=limit, batch_id=batch_id))


@router.get("/runs/page", response_model=ApiResponse[PageOut[BacktestRunOut]])
def get_runs_page(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    batch_id: str | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[PageOut[BacktestRunOut]]:
    result = repo.BacktestRepository(db, str(user.id)).list_runs_page(page=page, page_size=page_size, batch_id=batch_id)
    return ApiResponse(
        data=PageOut(
            items=result.items,
            total=result.total,
            page=result.page,
            page_size=result.page_size,
            pages=result.pages,
        )
    )


@router.get("/runs/{run_id}", response_model=ApiResponse[BacktestRunOut])
def get_run(
    run_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[BacktestRunOut]:
    row = repo.BacktestRepository(db, str(user.id)).get_run(run_id)
    if not row:
        raise HTTPException(status_code=404, detail="回测记录不存在")
    return ApiResponse(data=row)


@router.get("/batches", response_model=ApiResponse[list[dict[str, Any]]])
def get_batches(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> ApiResponse[list[dict[str, Any]]]:
    return ApiResponse(data=repo.BacktestRepository(db, str(user.id)).list_batches())


@router.post("/runs", response_model=ApiResponse[JobAccepted])
async def post_run(body: BacktestRunRequest, user: User = Depends(get_current_user)) -> ApiResponse[JobAccepted]:
    _validate_ma_windows(body.fast_window, body.slow_window)
    kind = "backtest.single"
    job_id = await enqueue_app_job(
        function=BACKTEST_FUNCS[kind],
        kind=kind,
        user_id=str(user.id),
        payload=body.model_dump(),
    )
    return ApiResponse(data=JobAccepted(job_id=job_id))


@router.post("/runs/batch", response_model=ApiResponse[JobAccepted])
async def post_batch(
    body: BatchBacktestRequest, user: User = Depends(get_current_user)
) -> ApiResponse[JobAccepted]:
    _validate_ma_windows(body.fast_window, body.slow_window)
    batch_id = uuid4().hex
    kind = "backtest.batch"
    job_id = await enqueue_app_job(
        function=BACKTEST_FUNCS[kind],
        kind=kind,
        user_id=str(user.id),
        payload=body.model_dump(),
        batch_id=batch_id,
    )
    return ApiResponse(data=JobAccepted(job_id=job_id, batch_id=batch_id))


@router.post("/optimize", response_model=ApiResponse[JobAccepted])
async def post_optimize(
    body: OptimizeBacktestRequest, user: User = Depends(get_current_user)
) -> ApiResponse[JobAccepted]:
    try:
        expand_ma_grid(body.space)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    batch_id = uuid4().hex
    kind = "backtest.optimize"
    job_id = await enqueue_app_job(
        function=BACKTEST_FUNCS[kind],
        kind=kind,
        user_id=str(user.id),
        payload=body.model_dump(),
        batch_id=batch_id,
    )
    return ApiResponse(data=JobAccepted(job_id=job_id, batch_id=batch_id))


@router.get("/optimize/{batch_id}", response_model=ApiResponse[OptimizeSummaryOut])
def get_optimize(
    batch_id: str,
    objective: str = Query(default="sharpe_ratio"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[OptimizeSummaryOut]:
    return ApiResponse(data=repo.BacktestRepository(db, str(user.id)).summarize_optimize(batch_id, objective=objective))

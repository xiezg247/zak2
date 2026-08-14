from __future__ import annotations

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
    StrategyInfo,
    StrategyProfileOut,
)
from app.services import backtest_repo as repo
from app.services.arq_jobs import BACKTEST_FUNCS, enqueue_app_job
from app.services.backtest_engine import PROFILES, STRATEGIES

router = APIRouter(prefix="/backtest", tags=["backtest"])


@router.get("/strategies", response_model=list[StrategyInfo])
def list_strategies(user: User = Depends(get_current_user)) -> list[StrategyInfo]:
    _ = user
    return [StrategyInfo(**s) for s in STRATEGIES]


@router.get("/profiles", response_model=list[StrategyProfileOut])
def list_profiles(user: User = Depends(get_current_user)) -> list[StrategyProfileOut]:
    _ = user
    return [StrategyProfileOut(**p) for p in PROFILES]


@router.get("/runs", response_model=list[BacktestRunOut])
def get_runs(
    limit: int = Query(default=50, ge=1, le=200),
    batch_id: str | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[BacktestRunOut]:
    return repo.list_runs(db, str(user.id), limit=limit, batch_id=batch_id)


@router.get("/runs/{run_id}", response_model=BacktestRunOut)
def get_run(
    run_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BacktestRunOut:
    row = repo.get_run(db, str(user.id), run_id)
    if not row:
        raise HTTPException(status_code=404, detail="回测记录不存在")
    return row


@router.get("/batches")
def get_batches(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[dict]:
    return repo.list_batches(db, str(user.id))


@router.post("/runs", response_model=JobAccepted)
async def post_run(body: BacktestRunRequest, user: User = Depends(get_current_user)) -> JobAccepted:
    kind = "backtest.single"
    job_id = await enqueue_app_job(
        function=BACKTEST_FUNCS[kind],
        kind=kind,
        user_id=str(user.id),
        payload=body.model_dump(),
    )
    return JobAccepted(job_id=job_id)


@router.post("/runs/batch", response_model=JobAccepted)
async def post_batch(body: BatchBacktestRequest, user: User = Depends(get_current_user)) -> JobAccepted:
    batch_id = uuid4().hex
    kind = "backtest.batch"
    job_id = await enqueue_app_job(
        function=BACKTEST_FUNCS[kind],
        kind=kind,
        user_id=str(user.id),
        payload=body.model_dump(),
        batch_id=batch_id,
    )
    return JobAccepted(job_id=job_id, batch_id=batch_id)

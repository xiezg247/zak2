from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.db import SessionLocal, get_db
from app.jobs.store import job_store
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
from app.services.backtest_engine import PROFILES, STRATEGIES

router = APIRouter(prefix="/backtest", tags=["backtest"])
_executor = ThreadPoolExecutor(max_workers=2)


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


def _run_single_job(job_id: str, user_id: str, payload: dict) -> None:
    job_store.update(job_id, status="running", progress=0.1)
    db = SessionLocal()
    try:
        req = BacktestRunRequest.model_validate(payload)
        out = repo.execute_single(db, user_id, req)
        job_store.update(job_id, status="success", progress=1.0, result_ref=out.id)
    except HTTPException as exc:
        job_store.update(job_id, status="failed", error=str(exc.detail))
    except Exception as exc:  # noqa: BLE001
        job_store.update(job_id, status="failed", error=str(exc))
    finally:
        db.close()


def _run_batch_job(job_id: str, user_id: str, payload: dict, batch_id: str) -> None:
    job_store.update(job_id, status="running", progress=0.05)
    db = SessionLocal()
    try:
        req = BatchBacktestRequest.model_validate(payload)
        total = len(req.symbols)
        last_id = None
        for index, symbol in enumerate(req.symbols):
            single = BacktestRunRequest(
                vt_symbol=symbol,
                strategy=req.strategy,
                interval=req.interval,
                start_date=req.start_date,
                end_date=req.end_date,
                fast_window=req.fast_window,
                slow_window=req.slow_window,
                capital=req.capital,
            )
            try:
                out = repo.execute_single(db, user_id, single, batch_id=batch_id, source="batch")
                last_id = out.id
            except Exception as exc:  # noqa: BLE001
                # 单票失败不中断整批
                job_store.update(job_id, error=f"{symbol}: {exc}")
            job_store.update(job_id, progress=round((index + 1) / total, 4))
        job_store.update(job_id, status="success", progress=1.0, result_ref=last_id or batch_id)
    except Exception as exc:  # noqa: BLE001
        job_store.update(job_id, status="failed", error=str(exc))
    finally:
        db.close()


@router.post("/runs", response_model=JobAccepted)
def post_run(body: BacktestRunRequest, user: User = Depends(get_current_user)) -> JobAccepted:
    job = job_store.create("backtest.single", meta={"user_id": str(user.id)})
    _executor.submit(_run_single_job, job.id, str(user.id), body.model_dump())
    return JobAccepted(job_id=job.id)


@router.post("/runs/batch", response_model=JobAccepted)
def post_batch(body: BatchBacktestRequest, user: User = Depends(get_current_user)) -> JobAccepted:
    batch_id = uuid4().hex
    job = job_store.create("backtest.batch", meta={"user_id": str(user.id), "batch_id": batch_id})
    _executor.submit(_run_batch_job, job.id, str(user.id), body.model_dump(), batch_id)
    return JobAccepted(job_id=job.id, batch_id=batch_id)

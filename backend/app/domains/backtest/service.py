"""回测域编排：记录查询、批/优化入队与策略元数据。"""

from __future__ import annotations

from uuid import uuid4

from sqlalchemy.orm import Session

from app.core.errors import NotFound, ValidationFailed
from app.domains.backtest.backtest_engine import PROFILES, STRATEGIES
from app.domains.backtest.backtest_optimize import expand_ma_grid
from app.domains.backtest.repository import BacktestRepository
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
from app.schemas.common import PageOut
from app.services.ops.arq_jobs import BACKTEST_FUNCS, enqueue_app_job

MA_WINDOW_STRATEGIES = {"double_ma", "trend_ma", "medium_swing"}


def _validate_ma_windows(strategy: str, fast: int, slow: int) -> None:
    if strategy in MA_WINDOW_STRATEGIES and fast >= slow:
        raise ValidationFailed("fast_window 须小于 slow_window")


class BacktestService:
    """回测域服务：承接 /backtest 各端点的查询与入队逻辑。"""

    @staticmethod
    def list_strategies() -> list[StrategyInfo]:
        return [StrategyInfo(**s) for s in STRATEGIES]

    @staticmethod
    def list_profiles() -> list[StrategyProfileOut]:
        return [StrategyProfileOut(**p) for p in PROFILES]

    @staticmethod
    def list_runs(
        db: Session, user_id: str, *, limit: int = 50, batch_id: str | None = None
    ) -> list[BacktestRunOut]:
        return BacktestRepository(db, user_id).list_runs(limit=limit, batch_id=batch_id)

    @staticmethod
    def list_runs_page(
        db: Session,
        user_id: str,
        *,
        page: int = 1,
        page_size: int = 20,
        batch_id: str | None = None,
    ) -> PageOut[BacktestRunOut]:
        result = BacktestRepository(db, user_id).list_runs_page(
            page=page, page_size=page_size, batch_id=batch_id
        )
        return PageOut.from_page(result)

    @staticmethod
    def get_run(db: Session, user_id: str, run_id: str) -> BacktestRunOut:
        row = BacktestRepository(db, user_id).get_run(run_id)
        if not row:
            raise NotFound("回测记录不存在")
        return row

    @staticmethod
    def list_batches(db: Session, user_id: str) -> list[BacktestBatchOut]:
        return BacktestRepository(db, user_id).list_batches()

    @staticmethod
    async def enqueue_single(user_id: str, body: BacktestRunRequest) -> JobAccepted:
        _validate_ma_windows(body.strategy, body.fast_window, body.slow_window)
        kind = "backtest.single"
        job_id = await enqueue_app_job(
            function=BACKTEST_FUNCS[kind],
            kind=kind,
            user_id=user_id,
            payload=body.model_dump(),
        )
        return JobAccepted(job_id=job_id)

    @staticmethod
    async def enqueue_batch(user_id: str, body: BatchBacktestRequest) -> JobAccepted:
        _validate_ma_windows(body.strategy, body.fast_window, body.slow_window)
        batch_id = uuid4().hex
        kind = "backtest.batch"
        job_id = await enqueue_app_job(
            function=BACKTEST_FUNCS[kind],
            kind=kind,
            user_id=user_id,
            payload=body.model_dump(),
            batch_id=batch_id,
        )
        return JobAccepted(job_id=job_id, batch_id=batch_id)

    @staticmethod
    async def enqueue_optimize(user_id: str, body: OptimizeBacktestRequest) -> JobAccepted:
        try:
            expand_ma_grid(body.space)
        except ValueError as exc:
            raise ValidationFailed(str(exc)) from exc
        batch_id = uuid4().hex
        kind = "backtest.optimize"
        job_id = await enqueue_app_job(
            function=BACKTEST_FUNCS[kind],
            kind=kind,
            user_id=user_id,
            payload=body.model_dump(),
            batch_id=batch_id,
        )
        return JobAccepted(job_id=job_id, batch_id=batch_id)

    @staticmethod
    def summarize_optimize(
        db: Session,
        user_id: str,
        batch_id: str,
        *,
        objective: str = "sharpe_ratio",
    ) -> OptimizeSummaryOut:
        return BacktestRepository(db, user_id).summarize_optimize(batch_id, objective=objective)

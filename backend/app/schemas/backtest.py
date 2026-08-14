from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class BacktestRunOut(BaseModel):
    id: str
    vt_symbol: str
    strategy: str
    interval: str
    start_date: str
    end_date: str
    total_return: float | None = None
    max_drawdown: float | None = None
    sharpe_ratio: float | None = None
    trade_count: int | None = None
    source: str
    batch_id: str | None = None
    statistics: dict[str, Any] = Field(default_factory=dict)
    created_at: str
    equity_curve: list[dict[str, Any]] = Field(default_factory=list)
    trades: list[dict[str, Any]] = Field(default_factory=list)
    engine: str | None = None
    status: str = "success"
    error_message: str | None = None
    params: dict[str, Any] = Field(default_factory=dict)


class BacktestRunRequest(BaseModel):
    vt_symbol: str = Field(description="如 600519.SSE")
    strategy: str = "double_ma"
    interval: str = "d"
    start_date: str = "2020-01-01"
    end_date: str = "2026-12-31"
    fast_window: int = Field(default=5, ge=2, le=120)
    slow_window: int = Field(default=20, ge=3, le=250)
    capital: float = Field(default=100_000, gt=0)
    rate: float = Field(default=0.00045, ge=0)
    slippage: float = Field(default=0.0, ge=0)
    stamp_duty: float = Field(default=0.0005, ge=0)
    adx_period: int = Field(default=14, ge=2, le=120)
    adx_threshold: float = Field(default=25.0, ge=0)
    trailing_stop_pct: float = Field(default=0.12, gt=0, le=1)


class BatchBacktestRequest(BaseModel):
    symbols: list[str] = Field(min_length=1, max_length=50)
    strategy: str = "double_ma"
    interval: str = "d"
    start_date: str = "2020-01-01"
    end_date: str = "2026-12-31"
    fast_window: int = 5
    slow_window: int = 20
    capital: float = 100_000
    rate: float = Field(default=0.00045, ge=0)
    slippage: float = Field(default=0.0, ge=0)
    stamp_duty: float = Field(default=0.0005, ge=0)
    adx_period: int = Field(default=14, ge=2, le=120)
    adx_threshold: float = Field(default=25.0, ge=0)
    trailing_stop_pct: float = Field(default=0.12, gt=0, le=1)


class OptimizeBacktestRequest(BaseModel):
    vt_symbol: str = Field(description="如 600519.SSE")
    strategy: str = "double_ma"
    interval: str = "d"
    start_date: str = "2020-01-01"
    end_date: str = "2026-12-31"
    capital: float = Field(default=100_000, gt=0)
    rate: float = Field(default=0.00045, ge=0)
    slippage: float = Field(default=0.0, ge=0)
    stamp_duty: float = Field(default=0.0005, ge=0)
    adx_period: int = Field(default=14, ge=2, le=120)
    adx_threshold: float = Field(default=25.0, ge=0)
    trailing_stop_pct: float = Field(default=0.12, gt=0, le=1)
    space: dict[str, list[int]] = Field(default_factory=dict)
    objective: str = "sharpe_ratio"


class OptimizeSummaryOut(BaseModel):
    batch_id: str
    objective: str
    best: BacktestRunOut | None = None
    runs: list[BacktestRunOut] = Field(default_factory=list)


class StrategyInfo(BaseModel):
    id: str
    name: str
    interval: str
    description: str
    implemented: bool = True
    engine: str = "vnpy"


class StrategyProfileOut(BaseModel):
    profile_id: str
    name: str
    description: str
    fast_window: int
    slow_window: int
    capital: float


class JobAccepted(BaseModel):
    job_id: str
    batch_id: str | None = None

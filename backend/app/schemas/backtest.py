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


class BacktestRunRequest(BaseModel):
    vt_symbol: str = Field(description="如 600519.SSE")
    strategy: str = "double_ma"
    interval: str = "d"
    start_date: str = "2020-01-01"
    end_date: str = "2026-12-31"
    fast_window: int = Field(default=5, ge=2, le=120)
    slow_window: int = Field(default=20, ge=3, le=250)
    capital: float = Field(default=100_000, gt=0)


class BatchBacktestRequest(BaseModel):
    symbols: list[str] = Field(min_length=1, max_length=20)
    strategy: str = "double_ma"
    interval: str = "d"
    start_date: str = "2020-01-01"
    end_date: str = "2026-12-31"
    fast_window: int = 5
    slow_window: int = 20
    capital: float = 100_000


class StrategyInfo(BaseModel):
    id: str
    name: str
    interval: str
    description: str
    implemented: bool = True


class StrategyProfileOut(BaseModel):
    profile_id: str
    name: str
    description: str


class JobAccepted(BaseModel):
    job_id: str
    batch_id: str | None = None

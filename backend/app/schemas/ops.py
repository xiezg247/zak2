from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class HealthOut(BaseModel):
    postgres: dict[str, Any]
    redis: dict[str, Any]
    llm: dict[str, Any]
    tushare_configured: bool
    mcp: dict[str, Any] = Field(default_factory=dict)
    note: str = ""


class SchedulerConfigOut(BaseModel):
    id: str
    config: dict[str, Any]
    updated_at: str | None = None


class SchedulerConfigPut(BaseModel):
    config: dict[str, Any]


class JobEnabledPatch(BaseModel):
    enabled: bool


class JobLastRun(BaseModel):
    last_run_at: str
    last_message: str = ""
    last_success: bool | None = None


class SchedulerJobOut(BaseModel):
    job_id: str
    name: str
    description: str
    runnable: bool
    run_hint: str | None = None
    enabled: bool = False
    cron_hour: int | None = None
    cron_minute: int | None = None
    cron_day_of_week: str | None = None
    cron_hours: str | None = None
    interval_seconds: int | None = None
    last_run: JobLastRun | None = None


class PurgeResult(BaseModel):
    deleted: dict[str, int]
    total: int
    message: str


class SyncResult(BaseModel):
    success: bool = True
    message: str
    skipped: bool = False
    extra: dict[str, Any] = Field(default_factory=dict)


class BarsOverviewOut(BaseModel):
    interval: str
    symbol_count: int
    min_start: str | None = None
    max_end: str | None = None
    as_of_trade_date: str | None = None
    ok_count: int = 0
    stale_count: int = 0
    unknown_count: int = 0


class JobAccepted(BaseModel):
    job_id: str
    kind: str


class McpToolOut(BaseModel):
    name: str
    agent_name: str
    description: str = ""
    input_schema: dict[str, Any] = Field(default_factory=dict)


class McpToolsOut(BaseModel):
    enabled: bool
    configured: bool
    status: str
    tools: list[McpToolOut] = Field(default_factory=list)
    error: str | None = None

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class HealthPostgresOut(BaseModel):
    ok: bool
    error: str = ""
    url: str = ""


class HealthRedisOut(BaseModel):
    ok: bool
    url: str = ""
    updated_at: str | None = None
    quote_count: int = 0


class HealthLlmOut(BaseModel):
    configured: bool
    model: str = ""
    api_base: str = ""


class HealthMcpOut(BaseModel):
    configured: bool = False
    enabled: bool = False
    status: str = ""
    tool_count: int = 0
    tools: list[str] = Field(default_factory=list)
    error: str | None = None


class HealthSchedulerLockOut(BaseModel):
    ok: bool = False
    backend: str = "redis"
    ttl_seconds: int = 0
    key_prefix: str = ""


class HealthCollectorOut(BaseModel):
    running: bool = False
    provider: str | None = None
    status: str | None = None
    last_count: int = 0
    ts: str | None = None
    hint: str | None = None


class HealthOut(BaseModel):
    postgres: HealthPostgresOut
    redis: HealthRedisOut
    llm: HealthLlmOut
    tushare_configured: bool
    mcp: HealthMcpOut = Field(default_factory=HealthMcpOut)
    scheduler_lock: HealthSchedulerLockOut = Field(default_factory=HealthSchedulerLockOut)
    quote_collector: HealthCollectorOut = Field(default_factory=HealthCollectorOut)
    note: str = ""


class SchedulerConfigOut(BaseModel):
    id: str
    # 按 job config_attr 动态分组的配置（键为 job id，值为 cron/enabled 等），结构随 job 扩展。
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
    job_kind: Literal["runnable", "process", "planned"] = "runnable"
    runnable: bool
    run_hint: str | None = None
    status_label: str = "可跑"
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
    # 各任务自由附加的计数/明细（written/synced/rows…），保留开放结构。
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
    # 第三方 MCP 工具声明的 JSON Schema，结构由远端决定，保留原始对象。
    input_schema: dict[str, Any] = Field(default_factory=dict)


class McpToolsOut(BaseModel):
    enabled: bool
    configured: bool
    status: str
    tools: list[McpToolOut] = Field(default_factory=list)
    error: str | None = None

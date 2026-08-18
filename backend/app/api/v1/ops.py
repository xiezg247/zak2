from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.db import get_db
from app.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.ops import (
    BarsOverviewOut,
    HealthOut,
    JobAccepted,
    JobEnabledPatch,
    McpToolOut,
    McpToolsOut,
    PurgeResult,
    SchedulerConfigOut,
    SchedulerConfigPut,
    SchedulerJobOut,
    SyncResult,
)
from app.schemas.screener import JobOut
from app.services.ai import mcp_client
from app.services.ops import (
    auto_screen as ops_auto_screen,
)
from app.services.ops import (
    bars as ops_bars,
)
from app.services.ops import (
    health as ops_health,
)
from app.services.ops import (
    purge as ops_purge,
)
from app.services.ops import (
    scheduler as ops_scheduler,
)
from app.services.ops import (
    sync_calendar as ops_sync_calendar,
)
from app.services.ops import (
    sync_sector as ops_sync_sector,
)
from app.services.ops.catalog import JOBS_BY_ID
from app.services.ops.enqueue import enqueue_ops_job, list_ops_job_outs
from app.services.ops.runners import RUNNERS

router = APIRouter(prefix="/ops", tags=["ops"])


@router.get("/health", response_model=ApiResponse[HealthOut])
def get_health(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> ApiResponse[HealthOut]:
    _ = user
    return ApiResponse(data=ops_health.health_snapshot(db))


@router.post("/collector/force", response_model=ApiResponse[SyncResult])
def collector_force(user: User = Depends(get_current_user)) -> ApiResponse[SyncResult]:
    _ = user
    from app.services.quote_collect.control import force_collect_from_settings

    return ApiResponse(data=force_collect_from_settings())


@router.get("/mcp/tools", response_model=ApiResponse[McpToolsOut])
def get_mcp_tools(user: User = Depends(get_current_user)) -> ApiResponse[McpToolsOut]:
    _ = user
    probe = mcp_client.probe_connection()
    if not probe.get("enabled"):
        return ApiResponse(
            data=McpToolsOut(
                enabled=False,
                configured=False,
                status=str(probe.get("status") or "未启用"),
                tools=[],
            )
        )
    if probe.get("error") or str(probe.get("status") or "").startswith("连接失败"):
        return ApiResponse(
            data=McpToolsOut(
                enabled=True,
                configured=bool(probe.get("configured")),
                status=str(probe.get("status") or "连接失败"),
                tools=[],
                error=str(probe.get("error") or probe.get("status") or ""),
            )
        )
    try:
        tools = mcp_client.list_allowed_tools()
    except mcp_client.McpClientError as exc:
        return ApiResponse(
            data=McpToolsOut(
                enabled=True,
                configured=True,
                status=f"连接失败：{exc}",
                tools=[],
                error=str(exc),
            )
        )
    return ApiResponse(
        data=McpToolsOut(
            enabled=True,
            configured=True,
            status="已连接",
            tools=[
                McpToolOut(
                    name=t.name,
                    agent_name=mcp_client.agent_tool_name(t.name),
                    description=t.description,
                    input_schema=t.input_schema,
                )
                for t in tools
            ],
        )
    )


@router.get("/bars/overview", response_model=ApiResponse[BarsOverviewOut])
def get_bars_overview(
    interval: str = Query(default="d"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[BarsOverviewOut]:
    _ = user
    return ApiResponse(data=ops_bars.bars_overview(db, interval=interval))


@router.get("/scheduler/config", response_model=ApiResponse[SchedulerConfigOut])
def get_scheduler_config(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[SchedulerConfigOut]:
    _ = user
    return ApiResponse(data=ops_scheduler.load_scheduler_config(db))


@router.put("/scheduler/config", response_model=ApiResponse[SchedulerConfigOut])
def put_scheduler_config(
    body: SchedulerConfigPut,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[SchedulerConfigOut]:
    _ = user
    return ApiResponse(data=ops_scheduler.save_scheduler_config(db, body.config))


@router.get("/scheduler/jobs", response_model=ApiResponse[list[SchedulerJobOut]])
def get_scheduler_jobs(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[list[SchedulerJobOut]]:
    _ = user
    return ApiResponse(data=ops_scheduler.list_scheduler_jobs(db))


@router.patch("/scheduler/jobs/{job_id}", response_model=ApiResponse[SchedulerJobOut])
def patch_scheduler_job(
    job_id: str,
    body: JobEnabledPatch,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[SchedulerJobOut]:
    _ = user
    if job_id not in JOBS_BY_ID:
        raise HTTPException(status_code=404, detail="未知任务")
    kind = ops_scheduler.job_kind_for(job_id)
    if kind != "runnable" and body.enabled:
        detail = "独立进程请启动 quote-collector" if kind == "process" else "未实现任务不可启用"
        raise HTTPException(status_code=400, detail=detail)
    try:
        ops_scheduler.patch_job_enabled(db, job_id, body.enabled)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="未知任务") from exc
    for row in ops_scheduler.list_scheduler_jobs(db):
        if row.job_id == job_id:
            return ApiResponse(data=row)
    raise HTTPException(status_code=404, detail="未知任务")


@router.post("/scheduler/jobs/{job_id}/run", response_model=ApiResponse[JobAccepted])
async def run_scheduler_job(job_id: str, user: User = Depends(get_current_user)) -> ApiResponse[JobAccepted]:
    kind = ops_scheduler.job_kind_for(job_id)
    if kind != "runnable":
        detail = "独立进程请启动 quote-collector" if kind == "process" else "未实现任务不可执行"
        raise HTTPException(status_code=400, detail=detail)
    if job_id not in RUNNERS:
        raise HTTPException(
            status_code=501,
            detail=f"zak2 暂不支持执行该任务，请用 CLI：job run {job_id}",
        )
    arq_id = await enqueue_ops_job(job_id, user_id=str(user.id), force=True)
    return ApiResponse(data=JobAccepted(job_id=arq_id, kind=f"ops.{job_id}"))


@router.post("/sync/screen-intraday", response_model=ApiResponse[SyncResult])
def post_screen_intraday(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[SyncResult]:
    result = ops_auto_screen.screen_intraday(db, user_id=str(user.id))
    return ApiResponse(data=result)


@router.post("/sync/screen-post-close", response_model=ApiResponse[SyncResult])
def post_screen_post_close(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[SyncResult]:
    result = ops_auto_screen.screen_post_close(db, user_id=str(user.id))
    return ApiResponse(data=result)


@router.post("/cache/purge", response_model=ApiResponse[PurgeResult])
def post_cache_purge(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[PurgeResult]:
    _ = user
    return ApiResponse(data=ops_purge.purge_stale_cache(db))


@router.post("/sync/trade-calendar", response_model=ApiResponse[SyncResult])
def post_sync_calendar(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[SyncResult]:
    _ = user
    result = ops_sync_calendar.sync_trade_calendar(db)
    return ApiResponse(data=result)


@router.post("/sync/sector-flow", response_model=ApiResponse[SyncResult])
def post_sync_sector(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[SyncResult]:
    _ = user
    result = ops_sync_sector.sync_sector_flow_daily(db)
    return ApiResponse(data=result)


@router.get("/jobs/recent", response_model=ApiResponse[list[JobOut]])
async def list_ops_jobs(user: User = Depends(get_current_user)) -> ApiResponse[list[JobOut]]:
    _ = user
    return ApiResponse(data=await list_ops_job_outs(limit=50))

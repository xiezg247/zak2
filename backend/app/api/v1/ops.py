from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.db import SessionLocal, get_db
from app.jobs.store import job_store
from app.models.user import User
from app.schemas.ops import (
    BarsOverviewOut,
    HealthOut,
    JobAccepted,
    JobEnabledPatch,
    McpToolsOut,
    McpToolOut,
    PurgeResult,
    SchedulerConfigOut,
    SchedulerConfigPut,
    SchedulerJobOut,
    SyncResult,
)
from app.schemas.screener import JobOut
from app.services import (
    mcp_client,
    ops_auto_screen,
    ops_bars,
    ops_health,
    ops_purge,
    ops_scheduler,
    ops_sync_calendar,
    ops_sync_sector,
)
from app.services.ops_catalog import JOBS_BY_ID
from app.services.ops_runners import RUNNERS, needs_user_id

router = APIRouter(prefix="/ops", tags=["ops"])
_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="ops")

@router.get("/health", response_model=HealthOut)
def get_health(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> HealthOut:
    _ = user
    return HealthOut(**ops_health.health_snapshot(db))


@router.post("/collector/force", response_model=SyncResult)
def collector_force(user: User = Depends(get_current_user)) -> SyncResult:
    _ = user
    from app.services.quote_collect.control import force_collect_from_settings

    result = force_collect_from_settings()
    return SyncResult(success=bool(result.get("success")), message=str(result.get("message") or ""))


@router.get("/mcp/tools", response_model=McpToolsOut)
def get_mcp_tools(user: User = Depends(get_current_user)) -> McpToolsOut:
    _ = user
    probe = mcp_client.probe_connection()
    if not probe.get("enabled"):
        return McpToolsOut(
            enabled=False,
            configured=False,
            status=str(probe.get("status") or "未启用"),
            tools=[],
        )
    if probe.get("error") or str(probe.get("status") or "").startswith("连接失败"):
        return McpToolsOut(
            enabled=True,
            configured=bool(probe.get("configured")),
            status=str(probe.get("status") or "连接失败"),
            tools=[],
            error=str(probe.get("error") or probe.get("status") or ""),
        )
    try:
        tools = mcp_client.list_allowed_tools()
    except mcp_client.McpClientError as exc:
        return McpToolsOut(
            enabled=True,
            configured=True,
            status=f"连接失败：{exc}",
            tools=[],
            error=str(exc),
        )
    return McpToolsOut(
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


@router.get("/bars/overview", response_model=BarsOverviewOut)
def get_bars_overview(
    interval: str = Query(default="d"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BarsOverviewOut:
    _ = user
    return BarsOverviewOut(**ops_bars.bars_overview(db, interval=interval))


@router.get("/scheduler/config", response_model=SchedulerConfigOut)
def get_scheduler_config(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SchedulerConfigOut:
    _ = user
    return SchedulerConfigOut(**ops_scheduler.load_scheduler_config(db))


@router.put("/scheduler/config", response_model=SchedulerConfigOut)
def put_scheduler_config(
    body: SchedulerConfigPut,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SchedulerConfigOut:
    _ = user
    return SchedulerConfigOut(**ops_scheduler.save_scheduler_config(db, body.config))


@router.get("/scheduler/jobs", response_model=list[SchedulerJobOut])
def get_scheduler_jobs(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[SchedulerJobOut]:
    _ = user
    return [SchedulerJobOut(**row) for row in ops_scheduler.list_scheduler_jobs(db)]


@router.patch("/scheduler/jobs/{job_id}", response_model=SchedulerJobOut)
def patch_scheduler_job(
    job_id: str,
    body: JobEnabledPatch,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SchedulerJobOut:
    _ = user
    if job_id not in JOBS_BY_ID:
        raise HTTPException(status_code=404, detail="未知任务")
    kind = ops_scheduler.job_kind_for(job_id)
    if kind != "runnable" and body.enabled:
        detail = (
            "独立进程请启动 quote-collector"
            if kind == "process"
            else "未实现任务不可启用"
        )
        raise HTTPException(status_code=400, detail=detail)
    try:
        ops_scheduler.patch_job_enabled(db, job_id, body.enabled)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="未知任务") from exc
    for row in ops_scheduler.list_scheduler_jobs(db):
        if row["job_id"] == job_id:
            return SchedulerJobOut(**row)
    raise HTTPException(status_code=404, detail="未知任务")


def _run_ops_job(async_job_id: str, catalog_job_id: str, user_id: str = "") -> None:
    job_store.update(async_job_id, status="running", progress=0.1)
    runner = RUNNERS[catalog_job_id]
    db = SessionLocal()
    try:
        if needs_user_id(catalog_job_id):
            result = runner(db, user_id=user_id)
        else:
            result = runner(db)
        message = str(result.get("message") or "完成")
        if result.get("skipped"):
            job_store.update(async_job_id, status="success", progress=1.0, result_ref=message)
        elif catalog_job_id == "purge_stale_cache" or bool(result.get("success", True)):
            ok = True if catalog_job_id == "purge_stale_cache" else bool(result.get("success", True))
            job_store.update(
                async_job_id,
                status="success" if ok else "failed",
                progress=1.0,
                result_ref=message if ok else None,
                error=None if ok else message,
            )
        else:
            job_store.update(async_job_id, status="failed", error=message)
    except Exception as exc:  # noqa: BLE001
        job_store.update(async_job_id, status="failed", error=str(exc))
        try:
            ops_scheduler.save_job_run_meta(
                db, catalog_job_id, last_message=str(exc), last_success=False
            )
        except Exception:  # noqa: BLE001
            pass
    finally:
        db.close()


@router.post("/scheduler/jobs/{job_id}/run", response_model=JobAccepted)
def run_scheduler_job(job_id: str, user: User = Depends(get_current_user)) -> JobAccepted:
    kind = ops_scheduler.job_kind_for(job_id)
    if kind != "runnable":
        detail = (
            "独立进程请启动 quote-collector"
            if kind == "process"
            else "未实现任务不可执行"
        )
        raise HTTPException(status_code=400, detail=detail)
    if job_id not in RUNNERS:
        raise HTTPException(
            status_code=501,
            detail=f"zak2 暂不支持执行该任务，请用 CLI：job run {job_id}",
        )
    job = job_store.create(f"ops.{job_id}", meta={"user_id": str(user.id)})
    _executor.submit(_run_ops_job, job.id, job_id, str(user.id))
    return JobAccepted(job_id=job.id, kind=job.kind)


@router.post("/sync/screen-intraday", response_model=SyncResult)
def post_screen_intraday(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SyncResult:
    result = ops_auto_screen.screen_intraday(db, user_id=str(user.id))
    return SyncResult(
        success=bool(result.get("success")),
        message=str(result.get("message") or ""),
        skipped=bool(result.get("skipped")),
        extra={k: v for k, v in result.items() if k not in {"success", "message", "skipped"}},
    )


@router.post("/sync/screen-post-close", response_model=SyncResult)
def post_screen_post_close(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SyncResult:
    result = ops_auto_screen.screen_post_close(db, user_id=str(user.id))
    return SyncResult(
        success=bool(result.get("success")),
        message=str(result.get("message") or ""),
        skipped=bool(result.get("skipped")),
        extra={k: v for k, v in result.items() if k not in {"success", "message", "skipped"}},
    )


@router.post("/cache/purge", response_model=PurgeResult)
def post_cache_purge(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PurgeResult:
    _ = user
    return PurgeResult(**ops_purge.purge_stale_cache(db))


@router.post("/sync/trade-calendar", response_model=SyncResult)
def post_sync_calendar(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SyncResult:
    _ = user
    result = ops_sync_calendar.sync_trade_calendar(db)
    return SyncResult(
        success=bool(result.get("success")),
        message=str(result.get("message") or ""),
        skipped=bool(result.get("skipped")),
        extra={k: v for k, v in result.items() if k not in {"success", "message", "skipped"}},
    )


@router.post("/sync/sector-flow", response_model=SyncResult)
def post_sync_sector(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SyncResult:
    _ = user
    result = ops_sync_sector.sync_sector_flow_daily(db)
    return SyncResult(
        success=bool(result.get("success")),
        message=str(result.get("message") or ""),
        skipped=bool(result.get("skipped")),
        extra={k: v for k, v in result.items() if k not in {"success", "message", "skipped"}},
    )


@router.get("/jobs/recent", response_model=list[JobOut])
def list_ops_jobs(user: User = Depends(get_current_user)) -> list[JobOut]:
    _ = user
    rows = [j for j in job_store.list_recent() if str(j.kind).startswith("ops.")]
    return [
        JobOut(
            id=j.id,
            kind=j.kind,
            status=j.status,
            progress=j.progress,
            error=j.error,
            result_ref=j.result_ref,
            created_at=j.created_at,
            updated_at=j.updated_at,
        )
        for j in rows
    ]

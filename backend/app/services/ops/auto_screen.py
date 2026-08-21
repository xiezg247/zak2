"""盘中 / 盘后自动选股（Web 手动触发，写入 screener_runs）。"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.domains.screener import repository as repo
from app.domains.screener.engine import run_recipe_screen
from app.domains.screener.schemas import RecipeRunRequest
from app.schemas.ops import SyncResult
from app.domains.channels.notify import delivery as notify_delivery
from app.services.ops.scheduler import load_scheduler_config, save_job_run_meta

logger = logging.getLogger(__name__)

JOB_INTRADAY = "screen_intraday"
JOB_POST_CLOSE = "screen_post_close"
DEFAULT_INTRADAY_RECIPE = "intraday_multi"
DEFAULT_POST_CLOSE_RECIPE = "post_close_multi"

SCREEN_PUSH_TOP_N = 10


def _format_screen_lines(label: str, result: dict, run_id: str) -> str:
    """构造选股结果推送文本（Top N）。"""
    lines = [
        f"📊 {label}完成",
        f"配方 {result.get('condition')} 命中 {result.get('row_count')} 只"
        f"（扫描 {result.get('total_scanned')}，run={run_id}）",
    ]
    for i, row in enumerate((result.get("rows") or [])[:SCREEN_PUSH_TOP_N], 1):
        symbol = str(row.get("symbol") or "")
        name = str(row.get("name") or "")
        change_pct = row.get("change_pct")
        if isinstance(change_pct, (int, float)):
            lines.append(f"{i}. {symbol} {name} {change_pct:+.2f}%")
        else:
            lines.append(f"{i}. {symbol} {name}")
    return "\n".join(lines)


def _notify_screen_result(db: Session, *, user_id: str, job_id: str, label: str, result: dict, run_id: str) -> None:
    """推送选股结果到用户渠道；失败仅记录日志，不影响主流程。"""
    try:
        notify_delivery.deliver_text(
            db,
            user_id=user_id,
            event_type=f"ops.{job_id}",
            title=label,
            text=_format_screen_lines(label, result, run_id),
        )
    except Exception:
        logger.warning("选股结果推送失败：job=%s run=%s", job_id, run_id, exc_info=True)


def _run_auto_screen(
    db: Session,
    *,
    user_id: str,
    job_id: str,
    config_attr: str,
    default_recipe: str,
    label: str,
) -> SyncResult:
    """对当前用户跑配方选股并写入历史。

    Web「立即执行」视为 force：不校验交易时段（与桌面 force 语义接近）。
    """
    if not user_id:
        return SyncResult(success=False, message="缺少用户")

    cfg = (load_scheduler_config(db).config or {}).get(config_attr) or {}
    if not isinstance(cfg, dict):
        cfg = {}
    recipe_id = str(cfg.get("recipe_id") or default_recipe).strip() or default_recipe
    try:
        top_n = int(cfg.get("top_n") or 20)
    except (TypeError, ValueError):
        top_n = 20
    top_n = max(1, min(top_n, 200))

    prev = repo.ScreenerRunRepository(db, user_id).latest_run_symbols()
    req = RecipeRunRequest(recipe_id=recipe_id, top_n=top_n, hard_filter_template="balanced")
    try:
        # cron / 立即执行均用该 user_id 的权重（embedded 侧为 SCHEDULER_SCREEN_USER_ID）
        result = run_recipe_screen(req, previous_symbols=prev, db=db, user_id=user_id)
    except AppError as exc:
        message = str(exc.message)
        save_job_run_meta(db, job_id, last_message=message, last_success=False)
        return SyncResult(success=False, message=message)

    run = repo.ScreenerRunRepository(db, user_id).save_run(
        condition=str(result.get("condition") or label),
        source="scheduled",
        result={**result, "config": {**(result.get("config") or {}), "trigger": f"ops.{job_id}"}},
    )
    message = (
        f"{label}完成：{result.get('condition')} 命中 {result.get('row_count')} 只"
        f"（扫描 {result.get('total_scanned')}，run={run.id}）"
    )
    save_job_run_meta(db, job_id, last_message=message, last_success=True)
    _notify_screen_result(db, user_id=user_id, job_id=job_id, label=label, result=result, run_id=run.id)
    return SyncResult(
        success=True,
        message=message,
        extra={"run_id": run.id, "row_count": result.get("row_count")},
    )


def screen_intraday(db: Session, *, user_id: str) -> SyncResult:
    return _run_auto_screen(
        db,
        user_id=user_id,
        job_id=JOB_INTRADAY,
        config_attr="screen_intraday",
        default_recipe=DEFAULT_INTRADAY_RECIPE,
        label="盘中选股",
    )


def screen_post_close(db: Session, *, user_id: str) -> SyncResult:
    return _run_auto_screen(
        db,
        user_id=user_id,
        job_id=JOB_POST_CLOSE,
        config_attr="screen_post_close",
        default_recipe=DEFAULT_POST_CLOSE_RECIPE,
        label="盘后选股",
    )

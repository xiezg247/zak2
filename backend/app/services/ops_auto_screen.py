"""盘中 / 盘后自动选股（Web 手动触发，写入 screener_runs）。"""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.schemas.screener import RecipeRunRequest
from app.services.engine import run_recipe_screen
from app.services.ops_scheduler import load_scheduler_config, save_job_run_meta
from app.services import screener_repo as repo

JOB_INTRADAY = "screen_intraday"
JOB_POST_CLOSE = "screen_post_close"
DEFAULT_INTRADAY_RECIPE = "intraday_multi"
DEFAULT_POST_CLOSE_RECIPE = "post_close_multi"


def _run_auto_screen(
    db: Session,
    *,
    user_id: str,
    job_id: str,
    config_attr: str,
    default_recipe: str,
    label: str,
) -> dict[str, Any]:
    """对当前用户跑配方选股并写入历史。

    Web「立即执行」视为 force：不校验交易时段（与桌面 force 语义接近）。
    """
    if not user_id:
        return {"success": False, "message": "缺少用户", "skipped": False}

    cfg = (load_scheduler_config(db).get("config") or {}).get(config_attr) or {}
    if not isinstance(cfg, dict):
        cfg = {}
    recipe_id = str(cfg.get("recipe_id") or default_recipe).strip() or default_recipe
    try:
        top_n = int(cfg.get("top_n") or 20)
    except (TypeError, ValueError):
        top_n = 20
    top_n = max(1, min(top_n, 200))

    prev = repo.latest_run_symbols(db, user_id)
    req = RecipeRunRequest(recipe_id=recipe_id, top_n=top_n, hard_filter_template="balanced")
    try:
        # cron / 立即执行均用该 user_id 的权重（embedded 侧为 SCHEDULER_SCREEN_USER_ID）
        result = run_recipe_screen(req, previous_symbols=prev, db=db, user_id=user_id)
    except HTTPException as exc:
        message = str(exc.detail)
        save_job_run_meta(db, job_id, last_message=message, last_success=False)
        return {"success": False, "message": message}

    run = repo.save_run(
        db,
        user_id=user_id,
        condition=str(result.get("condition") or label),
        source="scheduled",
        result={**result, "config": {**(result.get("config") or {}), "trigger": f"ops.{job_id}"}},
    )
    message = (
        f"{label}完成：{result.get('condition')} 命中 {result.get('row_count')} 只"
        f"（扫描 {result.get('total_scanned')}，run={run.id}）"
    )
    save_job_run_meta(db, job_id, last_message=message, last_success=True)
    return {
        "success": True,
        "message": message,
        "run_id": run.id,
        "row_count": result.get("row_count"),
    }


def screen_intraday(db: Session, *, user_id: str) -> dict[str, Any]:
    return _run_auto_screen(
        db,
        user_id=user_id,
        job_id=JOB_INTRADAY,
        config_attr="screen_intraday",
        default_recipe=DEFAULT_INTRADAY_RECIPE,
        label="盘中选股",
    )


def screen_post_close(db: Session, *, user_id: str) -> dict[str, Any]:
    return _run_auto_screen(
        db,
        user_id=user_id,
        job_id=JOB_POST_CLOSE,
        config_attr="screen_post_close",
        default_recipe=DEFAULT_POST_CLOSE_RECIPE,
        label="盘后选股",
    )

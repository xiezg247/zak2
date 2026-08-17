from __future__ import annotations

import importlib.util
import logging
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeout
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.services import skills_catalog

_logger = logging.getLogger(__name__)

SKILL_TIMEOUT_SEC = 5.0


@dataclass
class SkillContext:
    db: Session
    user_id: str


def run_skill_module(skill_id: str, ctx: SkillContext, args: dict[str, Any] | None = None) -> Any:
    try:
        skill_dir = skills_catalog.resolve_skill_dir(skill_id)
    except ValueError as exc:
        return {"error": str(exc)}

    path = skill_dir / "skill.py"
    if not path.is_file():
        return {"error": f"skill 不可运行或不存在：{skill_id}"}

    try:
        spec = importlib.util.spec_from_file_location(f"zak2_skill_{skill_id}", path)
        if spec is None or spec.loader is None:
            return {"error": f"无法加载 skill：{skill_id}"}
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        run_fn = getattr(mod, "run", None)
        if not callable(run_fn):
            return {"error": f"skill 缺少 run()：{skill_id}"}

        payload = dict(args or {})

        def _call() -> Any:
            return run_fn(ctx, payload)

        pool = ThreadPoolExecutor(max_workers=1)
        timed_out = False
        try:
            fut = pool.submit(_call)
            return fut.result(timeout=SKILL_TIMEOUT_SEC)
        except FuturesTimeout:
            timed_out = True
            # Soft timeout: worker may still run; do not reuse ctx.db after return.
            return {"error": f"skill 执行超时（>{SKILL_TIMEOUT_SEC}s）：{skill_id}"}
        finally:
            pool.shutdown(wait=not timed_out)
    except FuturesTimeout:
        return {"error": f"skill 执行超时（>{SKILL_TIMEOUT_SEC}s）：{skill_id}"}
    except Exception as exc:  # noqa: BLE001
        _logger.warning("skill %s failed: %s", skill_id, exc)
        return {"error": str(exc)}

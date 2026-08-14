"""ARQ WorkerSettings：`arq app.worker.settings.WorkerSettings`（不含回测）。"""

from __future__ import annotations

from arq.connections import RedisSettings

from app.core.settings import get_settings
from app.worker.tasks import run_ops_job
from app.worker.tasks_screener import (
    run_screener_condition,
    run_screener_pattern,
    run_screener_recipe,
    run_screener_reference_peer,
)

_settings = get_settings()


class WorkerSettings:
    functions = [
        run_ops_job,
        run_screener_condition,
        run_screener_recipe,
        run_screener_pattern,
        run_screener_reference_peer,
    ]
    max_jobs = 2
    redis_settings = RedisSettings.from_dsn(_settings.redis_url)
    queue_name = _settings.arq_queue_name

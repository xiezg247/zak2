"""ARQ WorkerSettings：`arq app.worker.settings.WorkerSettings`。"""

from __future__ import annotations

from arq.connections import RedisSettings

from app.core.settings import get_settings
from app.worker.tasks import run_ops_job

_settings = get_settings()


class WorkerSettings:
    functions = [run_ops_job]
    max_jobs = 2
    redis_settings = RedisSettings.from_dsn(_settings.redis_url)
    queue_name = _settings.arq_queue_name

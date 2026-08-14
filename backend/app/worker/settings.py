"""ARQ WorkerSettings：`arq app.worker.settings.WorkerSettings`。"""

from __future__ import annotations

from arq.connections import RedisSettings

from app.core.settings import get_settings
from app.worker.tasks import run_ops_job
from app.worker.tasks_backtest import run_backtest_batch, run_backtest_single
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
        run_backtest_single,
        run_backtest_batch,
    ]
    max_jobs = 2
    redis_settings = RedisSettings.from_dsn(_settings.redis_url)
    queue_name = _settings.arq_queue_name

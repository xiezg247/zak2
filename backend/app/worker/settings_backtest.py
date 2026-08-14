"""ARQ backtest WorkerSettings：`arq app.worker.settings_backtest.WorkerSettings`。"""

from __future__ import annotations

from arq.connections import RedisSettings

from app.core.settings import get_settings
from app.worker.tasks_backtest import (
    run_backtest_batch,
    run_backtest_optimize,
    run_backtest_single,
)

_settings = get_settings()


class WorkerSettings:
    functions = [
        run_backtest_single,
        run_backtest_batch,
        run_backtest_optimize,
    ]
    max_jobs = 2
    redis_settings = RedisSettings.from_dsn(_settings.redis_url)
    queue_name = _settings.arq_backtest_queue_name

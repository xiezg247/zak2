"""ARQ worker 日志配置（配合 ``arq --custom-log-dict``）。

- 丢弃 arq 默认的逐任务 ``→``/``←`` 两行（含冗余 job_id 与原始参数/结果转储），
  改为在 ``run_ops_job`` 内输出单行精简结果。
- 其余 arq 日志（启动、健康检查、重试/中止/异常）原样保留。
"""

from __future__ import annotations

import logging
from typing import Any

_FORMAT = "%(asctime)s %(levelname)-7s %(message)s"
_DATEFMT = "%H:%M:%S"


class DropArqJobLines(logging.Filter):
    """丢弃 arq 默认的逐任务 start/complete 日志。"""

    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.msg
        return not (isinstance(msg, str) and ("→" in msg or "←" in msg))


LOG_CONFIG: dict[str, Any] = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "drop_arq_job_lines": {"()": "app.worker.logconfig.DropArqJobLines"},
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "standard",
            "filters": ["drop_arq_job_lines"],
        },
    },
    "formatters": {
        "standard": {"format": _FORMAT, "datefmt": _DATEFMT},
    },
    "root": {"handlers": ["console"], "level": "INFO"},
}

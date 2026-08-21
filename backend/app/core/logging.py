"""集中日志配置。

统一根日志的格式与级别，供 ``create_app`` 在启动时调用一次。

设计要点：

- **幂等**：仅在根 logger 尚无 handler 时补充，避免与 uvicorn 自带的
  日志配置（``--log-level`` 等）冲突；uvicorn 已配置时仅校准级别。
- **request_id**：为所有 root handler 挂载 ``RequestIdFilter``，
  使现有 ``getLogger`` 输出自动携带当前请求上下文 id。
- **独立运行友好**：脚本 / 测试等非 uvicorn 场景下也能得到统一输出。
"""

from __future__ import annotations

import logging

from app.core.request_logging import RequestIdFilter, install_request_id_filter

_FMT = "%(asctime)s %(levelname)-7s %(name)s | %(request_id)s | %(message)s"


def configure_logging(level: str = "INFO") -> None:
    """配置根 logger（幂等）。"""
    root = logging.getLogger()
    root.setLevel(level.upper())

    if root.handlers:
        # uvicorn 已接管根 logger，仅同步级别，不重复挂 handler
        for handler in root.handlers:
            handler.setLevel(level.upper())
    else:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(_FMT))
        root.addHandler(handler)

    install_request_id_filter()

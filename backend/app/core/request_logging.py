"""日志注入 request_id：挂在 root handler 上，现有 logger 自动携带。"""

from __future__ import annotations

import logging

from app.core.request_context import get_request_id

_FMT = "%(asctime)s %(levelname)-7s %(name)s | %(request_id)s | %(message)s"


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_request_id() or "-"
        return True


def install_request_id_filter() -> None:
    root = logging.getLogger()
    if not root.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(_FMT))
        root.addHandler(handler)
    for handler in root.handlers:
        if not any(isinstance(f, RequestIdFilter) for f in handler.filters):
            handler.addFilter(RequestIdFilter())

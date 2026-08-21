"""RequestIdFilter 单测：现有 logger 输出自动携带 request_id。"""

from __future__ import annotations

import logging

from app.core.logging import configure_logging
from app.core.request_context import _request_ctx, _reset
from app.core.request_logging import RequestIdFilter, install_request_id_filter


def _capture(record) -> str:
    return record.request_id  # type: ignore[attr-defined]


def test_filter_without_context_uses_dash() -> None:
    record = logging.LogRecord("t", logging.INFO, __file__, 1, "m", (), None)
    assert RequestIdFilter().filter(record) is True
    assert record.request_id == "-"  # type: ignore[attr-defined]


def test_filter_with_context_uses_request_id() -> None:
    from app.core.request_context import RequestContext

    ctx = RequestContext(request_id="rid-1", method="GET", path="/x")
    token = _request_ctx.set(ctx)
    try:
        record = logging.LogRecord("t", logging.INFO, __file__, 1, "m", (), None)
        RequestIdFilter().filter(record)
        assert record.request_id == "rid-1"  # type: ignore[attr-defined]
    finally:
        _reset(token)


def test_install_filter_idempotent_on_root_handlers() -> None:
    root = logging.getLogger()
    original_handlers = list(root.handlers)
    original_level = root.level
    try:
        root.handlers = []
        install_request_id_filter()
        first = sum(1 for h in root.handlers for f in h.filters if isinstance(f, RequestIdFilter))
        install_request_id_filter()
        second = sum(1 for h in root.handlers for f in h.filters if isinstance(f, RequestIdFilter))
        assert first >= 1
        assert second == first  # 不重复挂
    finally:
        root.handlers = original_handlers
        root.setLevel(original_level)


def test_configure_logging_has_request_id_in_format() -> None:
    root = logging.getLogger()
    original_handlers = list(root.handlers)
    original_level = root.level
    try:
        root.handlers = []
        configure_logging("INFO")
        fmt = root.handlers[0].formatter._fmt
        assert "%(request_id)s" in fmt
    finally:
        root.handlers = original_handlers
        root.setLevel(original_level)

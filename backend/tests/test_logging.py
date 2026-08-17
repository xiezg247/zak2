"""集中日志配置单测：锁定幂等行为。"""

from __future__ import annotations

import logging

from app.core.logging import configure_logging


def test_configure_logging_idempotent() -> None:
    root = logging.getLogger()
    original_handlers = list(root.handlers)
    original_level = root.level

    try:
        configure_logging("WARNING")
        first_count = len(root.handlers)
        assert root.level == logging.WARNING

        configure_logging("DEBUG")
        second_count = len(root.handlers)
        assert root.level == logging.DEBUG

        # 无论是否已存在 handler，都不重复添加
        assert second_count == first_count
    finally:
        root.handlers = original_handlers
        root.setLevel(original_level)


def test_configure_logging_sets_formatter() -> None:
    root = logging.getLogger()
    original_handlers = list(root.handlers)
    original_level = root.level

    try:
        root.handlers = []
        configure_logging("INFO")
        assert len(root.handlers) == 1
        assert root.handlers[0].formatter is not None
    finally:
        root.handlers = original_handlers
        root.setLevel(original_level)

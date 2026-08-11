"""TickFlow 官方 SDK 薄封装（非 vnpy_tickflow）。"""

from __future__ import annotations

from typing import Any


def get_tickflow_client(*, api_key: str = "") -> Any:
    from tickflow import TickFlow

    key = (api_key or "").strip()
    if key:
        return TickFlow(api_key=key)
    return TickFlow.free()

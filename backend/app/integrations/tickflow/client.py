"""TickFlow 官方 SDK 薄封装（非 vnpy_tickflow）。"""

from __future__ import annotations

from typing import Any


def get_tickflow_client(
    *,
    api_key: str = "",
    max_retries: int | None = None,
    timeout: float | None = None,
) -> Any:
    from tickflow import TickFlow

    kwargs: dict[str, Any] = {}
    if max_retries is not None:
        kwargs["max_retries"] = max_retries
    if timeout is not None:
        kwargs["timeout"] = timeout
    key = (api_key or "").strip()
    if key:
        return TickFlow(api_key=key, **kwargs)
    return TickFlow.free()

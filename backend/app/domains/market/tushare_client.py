"""Tushare Pro HTTP 薄封装（不依赖 tushare/pandas）。"""

from __future__ import annotations

from typing import Any

import httpx
from app.core.errors import UpstreamFailed

from app.core.settings import get_settings

DEFAULT_API_URL = "https://api.tushare.pro"


class TushareNotConfiguredError(RuntimeError):
    pass


def require_token() -> str:
    token = get_settings().tushare_token.strip()
    if not token:
        raise TushareNotConfiguredError("未配置 TUSHARE_TOKEN")
    return token


def query(api_name: str, params: dict[str, Any] | None = None, *, fields: str = "") -> list[dict[str, Any]]:
    token = require_token()
    url = DEFAULT_API_URL
    payload = {
        "api_name": api_name,
        "token": token,
        "params": params or {},
        "fields": fields,
    }
    try:
        with httpx.Client(timeout=60.0) as client:
            resp = client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPError as exc:
        raise UpstreamFailed(f"Tushare 网络错误：{exc}") from exc

    code = int(data.get("code") if data.get("code") is not None else -1)
    if code != 0:
        msg = str(data.get("msg") or data.get("message") or "未知错误")
        raise UpstreamFailed(f"Tushare {api_name}：{msg}")

    body = data.get("data") or {}
    field_names = list(body.get("fields") or [])
    items = list(body.get("items") or [])
    rows: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, (list, tuple)):
            continue
        rows.append({field_names[i]: item[i] for i in range(min(len(field_names), len(item)))})
    return rows


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default

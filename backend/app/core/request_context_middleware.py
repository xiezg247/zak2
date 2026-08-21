"""纯 ASGI 中间件：为每个请求写入请求上下文并回显 X-Request-ID。"""

from __future__ import annotations

from typing import Any

from app.core.request_context import (
    RequestContext,
    _new_request_id,
    _request_ctx,
    _reset,
)

_HEADER = "x-request-id"


class RequestContextMiddleware:
    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(self, scope: dict, receive: Any, send: Any) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers") or [])
        client_rid = headers.get(_HEADER.encode())
        rid = _new_request_id(client_rid.decode() if client_rid else None)
        ctx = RequestContext(
            request_id=rid,
            method=scope.get("method", ""),
            path=scope.get("path", ""),
        )
        token = _request_ctx.set(ctx)
        try:
            async def send_wrapper(message: dict) -> None:
                if message["type"] == "http.response.start":
                    headers = dict(message.get("headers") or [])
                    headers[b"X-Request-ID"] = rid.encode()
                    message = {**message, "headers": list(headers.items())}
                await send(message)

            await self.app(scope, receive, send_wrapper)
        finally:
            _reset(token)

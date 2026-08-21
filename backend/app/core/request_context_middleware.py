"""纯 ASGI 中间件：为每个请求写入请求上下文、回显 X-Request-ID。

未捕获异常在上下文存活时记录并返回统一 500；若交由 Starlette 外层
ServerErrorMiddleware 处理，上下文已被 reset，日志将丢失 request_id。
"""

from __future__ import annotations

from typing import Any

from starlette.requests import Request

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
        response_started = False
        try:
            async def send_wrapper(message: dict) -> None:
                nonlocal response_started
                if message["type"] == "http.response.start":
                    response_started = True
                    headers = dict(message.get("headers") or [])
                    headers[b"X-Request-ID"] = rid.encode()
                    message = {**message, "headers": list(headers.items())}
                await send(message)

            await self.app(scope, receive, send_wrapper)
        except Exception as exc:
            from app.api.errors import handle_unhandled

            response = handle_unhandled(Request(scope), exc)
            if not response_started:
                await response(scope, receive, send)
            else:
                raise
        finally:
            _reset(token)

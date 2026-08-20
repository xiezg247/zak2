"""全局异常处理器：统一错误响应结构 + 未捕获异常日志。

错误保持 HTTP 状态码，body 统一为 ``{code, message, detail, data}``：
- ``code``：HTTP 状态码
- ``message``：面向用户的可读信息
- ``detail``：与 FastAPI 原生 ``detail`` 对齐，兼容前端旧解析
- ``data``：恒为 ``None``

仅影响 JSON 响应；SSE / CSV 流式端点不受影响。
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.errors import AppError

logger = logging.getLogger(__name__)


def _json(status: int, message: str, detail: Any) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={"code": status, "message": message, "detail": detail, "data": None},
    )


def _first_validation_message(exc: RequestValidationError) -> str:
    errors = exc.errors()
    if not errors:
        return "参数校验失败"
    first = errors[0]
    loc = ".".join(str(x) for x in first.get("loc", []) if x != "body")
    msg = str(first.get("msg", "")).strip()
    return f"参数校验失败: {loc} {msg}".strip()


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        _ = request
        return _json(exc.status_code, exc.message, exc.detail)

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        _ = request
        detail = exc.detail
        message = detail if isinstance(detail, str) else str(detail)
        return _json(exc.status_code, message, detail)

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        _ = request
        return _json(422, _first_validation_message(exc), exc.errors())

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        return _json(500, "服务器内部错误", "服务器内部错误")

"""进程内请求上下文：request_id 与当前请求元数据。

由 RequestContextMiddleware 在请求开始时写入、请求结束 reset。
业务层经 get_request_id() / set_user_id() 读取或补全，避免透传参数。
"""

from __future__ import annotations

import re
import uuid
from contextvars import ContextVar, Token
from dataclasses import dataclass, field

_VALID_RID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


@dataclass
class RequestContext:
    request_id: str
    method: str
    path: str
    user_id: str | None = None


_request_ctx: ContextVar[RequestContext | None] = ContextVar("request_ctx", default=None)


def get_request_context() -> RequestContext | None:
    return _request_ctx.get()


def get_request_id() -> str:
    ctx = _request_ctx.get()
    return ctx.request_id if ctx else ""


def set_user_id(user_id: str) -> None:
    ctx = _request_ctx.get()
    if ctx is not None:
        ctx.user_id = user_id


def _new_request_id(client_id: str | None) -> str:
    if client_id and _VALID_RID.fullmatch(client_id):
        return client_id
    return uuid.uuid4().hex[:12]


def _reset(token: Token[RequestContext | None]) -> None:
    _request_ctx.reset(token)

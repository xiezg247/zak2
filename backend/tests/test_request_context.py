"""请求上下文单测：request_id 生成与透传规则、user_id 写入。"""

from __future__ import annotations

import re

from app.core.request_context import (
    _new_request_id,
    _request_ctx,
    _reset,
    get_request_context,
    get_request_id,
    set_user_id,
)
from app.core.request_context import RequestContext


def test_new_request_id_generates_uuid_hex12() -> None:
    rid = _new_request_id(None)
    assert re.fullmatch(r"[0-9a-f]{12}", rid)


def test_new_request_id_passthrough_valid() -> None:
    assert _new_request_id("abc-123_XYZ") == "abc-123_XYZ"


def test_new_request_id_strips_whitespace() -> None:
    assert _new_request_id(" abc ") == "abc"  # spec：strip 后校验，透传为 abc


def test_new_request_id_rejects_illegal() -> None:
    rid = _new_request_id("bad id with spaces!")  # 空格/感叹号非法
    assert re.fullmatch(r"[0-9a-f]{12}", rid)


def test_new_request_id_rejects_too_long() -> None:
    rid = _new_request_id("x" * 65)
    assert re.fullmatch(r"[0-9a-f]{12}", rid)


def test_get_request_id_without_context_is_empty() -> None:
    assert get_request_id() == ""


def test_context_lifecycle() -> None:
    ctx = RequestContext(request_id="r1", method="GET", path="/api/v1/x")
    token = _request_ctx.set(ctx)
    try:
        assert get_request_context() is ctx
        assert get_request_id() == "r1"
        set_user_id("u_9")
        assert ctx.user_id == "u_9"
    finally:
        _reset(token)


def test_set_user_id_without_context_is_noop() -> None:
    set_user_id("u_1")  # 不应抛异常

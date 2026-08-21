# 请求上下文与统一日志（Phase 7）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 FastAPI 后端引入请求级 `request_id`（透传/生成/回显），通过 `logging.Filter` 让现有 logger 自动携带，并增强未捕获异常日志——不改任何业务语义。

**Architecture:** 纯 ASGI 中间件在请求进入时把 `request_id` 与 method/path 写入 `ContextVar` 上下文；`logging.Filter` 挂在 root handler 上，为所有 `getLogger` 输出注入 `request_id` 字段；鉴权成功后 `set_user_id` 补用户上下文；`unhandled_exception_handler` 读取上下文增强日志。响应头回显 `X-Request-ID`。

**Tech Stack:** FastAPI、Starlette ASGI、`contextvars`、Python `logging`、pytest（含 caplog）。

## Global Constraints

- 不改业务语义：不重写现有日志语句、不改 REST/JWT/算法、不新增第三方依赖
- request_id 规则：优先透传 `X-Request-ID`（strip 后非空、长度 ≤64、字符集 `[A-Za-z0-9_-]`），非法则生成 `uuid4().hex[:12]`
- `RequestIdFilter` 挂 **root handler**（幂等：已有同名 Filter 不重复加），格式化串升级为 `"%(asctime)s %(levelname)-7s %(name)s | %(request_id)s | %(message)s"`
- 中间件用纯 ASGI（`app.scope`/`app.receive`/`app.send`），`finally` 中 `reset(ContextVar)`
- 仅 `unhandled_exception_handler` 增强日志；AppError/HTTPException/ValidationError handler 保持不记录
- commit 简体中文 `<type>(<scope>): <简述>`
- 每个 commit 前全量 `uv run pytest -q --tb=short` 绿

---

### Task 1: 请求上下文存储

**Files:**
- Create: `backend/app/core/request_context.py`
- Test: `backend/tests/test_request_context.py`

**Interfaces:**
- Consumes: 无
- Produces:
  - `get_request_context() -> RequestContext | None`
  - `get_request_id() -> str`（无上下文返回 `""`）
  - `set_user_id(user_id: str) -> None`（无上下文时 no-op）
  - `_new_request_id(client_id: str | None) -> str`（内部生成逻辑，供测试）
  - `RequestContext` dataclass：`request_id: str`、`method: str`、`path: str`、`user_id: str | None = None`
  - `_request_ctx: ContextVar` + `_reset()`（Task 2 中间件用）

- [ ] **Step 1: 写失败测试**

`backend/tests/test_request_context.py`：

```python
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
```

- [ ] **Step 2: 运行确认失败**

```bash
cd backend && uv run pytest tests/test_request_context.py -v
```
Expected: FAIL（`ModuleNotFoundError: No module named 'app.core.request_context'`）

- [ ] **Step 3: 写实现**

`backend/app/core/request_context.py`：

```python
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
```

- [ ] **Step 4: 运行确认通过**

```bash
cd backend && uv run pytest tests/test_request_context.py -v
```
Expected: 8 passed

- [ ] **Step 5: 全量回归 + 提交**

```bash
cd backend && uv run pytest -q --tb=short
cd /Users/xiezhigang/Projects/me/zak2 && git add backend/app/core/request_context.py backend/tests/test_request_context.py && git commit -m "$(cat <<'EOF'
feat(core): 新增请求上下文存储

ContextVar 保存 request_id/method/path/user_id，支持透传与生成。
EOF
)"
```

---

### Task 2: RequestIdFilter + logging 集成

**Files:**
- Create: `backend/app/core/request_logging.py`
- Modify: `backend/app/core/logging.py`
- Test: `backend/tests/test_request_logging.py`

**Interfaces:**
- Consumes: Task 1 的 `get_request_id()`
- Produces: `RequestIdFilter`（`logging.Filter` 子类）、`install_request_id_filter()`（在 root handler 上幂等挂载）
- Task 3 依赖：`configure_logging` 现在会挂载 Filter 并升级格式串

- [ ] **Step 1: 写失败测试**

`backend/tests/test_request_logging.py`：

```python
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
```

- [ ] **Step 2: 运行确认失败**

```bash
cd backend && uv run pytest tests/test_request_logging.py -v
```
Expected: FAIL（`ModuleNotFoundError: No module named 'app.core.request_logging'`）

- [ ] **Step 3: 写实现**

`backend/app/core/request_logging.py`：

```python
"""日志注入 request_id：挂在 root handler 上，现有 logger 自动携带。"""

from __future__ import annotations

import logging

from app.core.request_context import get_request_id

_FMT = "%(asctime)s %(levelname)-7s %(name)s | %(request_id)s | %(message)s"


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_request_id() or "-"
        return True


def install_request_id_filter() -> None:
    for handler in logging.getLogger().handlers:
        if not any(isinstance(f, RequestIdFilter) for f in handler.filters):
            handler.addFilter(RequestIdFilter())
```

`backend/app/core/logging.py` 全文替换（保持幂等语义，追加 Filter 与格式串）：

```python
"""集中日志配置。

统一根日志的格式与级别，供 ``create_app`` 在启动时调用一次。

设计要点：

- **幂等**：仅在根 logger 尚无 handler 时补充，避免与 uvicorn 自带的
  日志配置（``--log-level`` 等）冲突；uvicorn 已配置时仅校准级别。
- **request_id**：为所有 root handler 挂载 ``RequestIdFilter``，
  使现有 ``getLogger`` 输出自动携带当前请求上下文 id。
- **独立运行友好**：脚本 / 测试等非 uvicorn 场景下也能得到统一输出。
"""

from __future__ import annotations

import logging

from app.core.request_logging import RequestIdFilter, install_request_id_filter

_FMT = "%(asctime)s %(levelname)-7s %(name)s | %(request_id)s | %(message)s"


def configure_logging(level: str = "INFO") -> None:
    """配置根 logger（幂等）。"""
    root = logging.getLogger()
    root.setLevel(level.upper())

    if root.handlers:
        # uvicorn 已接管根 logger，仅同步级别，不重复挂 handler
        for handler in root.handlers:
            handler.setLevel(level.upper())
    else:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(_FMT))
        root.addHandler(handler)

    install_request_id_filter()
```

- [ ] **Step 4: 运行确认通过**

```bash
cd backend && uv run pytest tests/test_request_logging.py tests/test_logging.py -v
```
Expected: 5 passed（2 个新 + 3 个既有）

- [ ] **Step 5: 全量回归 + 提交**

```bash
cd backend && uv run pytest -q --tb=short
cd /Users/xiezhigang/Projects/me/zak2 && git add backend/app/core/request_logging.py backend/app/core/logging.py backend/tests/test_request_logging.py && git commit -m "$(cat <<'EOF'
feat(logging): root handler 注入 request_id Filter

configure_logging 幂等挂载 RequestIdFilter 并升级格式串，
现有 logger 输出自动携带当前请求 id。
EOF
)"
```

---

### Task 3: 纯 ASGI 中间件 + 应用接入

**Files:**
- Create: `backend/app/core/request_context_middleware.py`
- Modify: `backend/app/main.py`（`create_app` 内注册）
- Test: `backend/tests/test_request_context_middleware.py`

**Interfaces:**
- Consumes: Task 1 的 `RequestContext`、`_request_ctx`、`_reset`、`_new_request_id`
- Produces: `RequestContextMiddleware`（`StarletteMiddleware` 兼容：接受 `app`，实现 `__call__(scope, receive, send)`）
- Task 4 依赖：响应头 `X-Request-ID` 已回显

- [ ] **Step 1: 写失败测试**

`backend/tests/test_request_context_middleware.py`：

```python
"""中间件集成测试：request_id 回显 + 上下文写入。"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.request_context import get_request_id
from app.core.request_context_middleware import RequestContextMiddleware


def _app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(RequestContextMiddleware)

    @app.get("/echo")
    def echo() -> dict[str, str]:
        return {"request_id": get_request_id()}

    return app


def test_echo_header_passthrough() -> None:
    client = TestClient(_app())
    resp = client.get("/echo", headers={"X-Request-ID": "client-abc"})
    assert resp.status_code == 200
    assert resp.headers["X-Request-ID"] == "client-abc"
    assert resp.json() == {"request_id": "client-abc"}


def test_generates_and_echoes_when_absent() -> None:
    client = TestClient(_app())
    resp = client.get("/echo")
    assert resp.status_code == 200
    rid = resp.headers["X-Request-ID"]
    assert len(rid) == 12 and rid.isalnum()
    assert resp.json() == {"request_id": rid}


def test_invalid_header_generates_new() -> None:
    client = TestClient(_app())
    resp = client.get("/echo", headers={"X-Request-ID": "bad value!"})
    rid = resp.headers["X-Request-ID"]
    assert len(rid) == 12 and rid.isalnum()


def test_context_reset_after_request() -> None:
    from app.core.request_context import get_request_context

    client = TestClient(_app())
    client.get("/echo")
    assert get_request_context() is None
```

- [ ] **Step 2: 运行确认失败**

```bash
cd backend && uv run pytest tests/test_request_context_middleware.py -v
```
Expected: FAIL（`ModuleNotFoundError: No module named 'app.core.request_context_middleware'`）

- [ ] **Step 3: 写实现**

`backend/app/core/request_context_middleware.py`：

```python
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
```

`backend/app/main.py` 修改（在 `add_middleware(CORSMiddleware, ...)` 块之后追加）：

```python
    from app.core.request_context_middleware import RequestContextMiddleware

    app.add_middleware(RequestContextMiddleware)
```

- [ ] **Step 4: 运行确认通过**

```bash
cd backend && uv run pytest tests/test_request_context_middleware.py -v
```
Expected: 4 passed

- [ ] **Step 5: 全量回归 + 提交**

```bash
cd backend && uv run pytest -q --tb=short
cd /Users/xiezhigang/Projects/me/zak2 && git add backend/app/core/request_context_middleware.py backend/app/main.py backend/tests/test_request_context_middleware.py && git commit -m "$(cat <<'EOF'
feat(core): 纯 ASGI 请求上下文中间件

请求进入时写入 ContextVar 并回显 X-Request-ID，结束后 reset。
EOF
)"
```

---

### Task 4: 鉴权写入 user_id + 异常日志增强

**Files:**
- Modify: `backend/app/api/deps.py`（`get_current_user` 成功后）
- Modify: `backend/app/api/errors.py`（`unhandled_exception_handler`）
- Test: `backend/tests/test_request_context_integration.py`

**Interfaces:**
- Consumes: Task 1 的 `set_user_id()`；Task 3 的中间件（已在 main.py 注册）
- Produces: 无（行为增强）

- [ ] **Step 1: 写失败测试**

`backend/tests/test_request_context_integration.py`：

```python
"""集成：鉴权后 user_id 写入上下文；未捕获异常日志携带上下文。"""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.errors import register_exception_handlers
from app.core.request_context import get_request_context
from app.core.request_context_middleware import RequestContextMiddleware


def _app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(RequestContextMiddleware)
    register_exception_handlers(app)

    @app.get("/boom")
    def boom() -> None:
        raise RuntimeError("kaboom")

    @app.get("/context")
    def ctx() -> dict | None:
        c = get_request_context()
        return {"request_id": c.request_id, "user_id": c.user_id} if c else None

    return app


def test_unhandled_exception_log_has_context(caplog) -> None:
    client = TestClient(_app())
    with caplog.at_level(logging.ERROR, logger="app.api.errors"):
        resp = client.get("/boom", headers={"X-Request-ID": "req-1"})
    assert resp.status_code == 500
    assert any("req-1" in r.message for r in caplog.records)
    assert any("/boom" in r.message for r in caplog.records)


def test_middleware_runs_before_handlers() -> None:
    client = TestClient(_app())
    resp = client.get("/context")
    body = resp.json()
    assert body["request_id"] == resp.headers["X-Request-ID"]
    assert body["user_id"] is None
```

- [ ] **Step 2: 运行确认失败**

```bash
cd backend && uv run pytest tests/test_request_context_integration.py -v
```
Expected: FAIL（`test_unhandled_exception_log_has_context` —— 异常日志尚未携带 request_id）

- [ ] **Step 3: 写实现**

`backend/app/api/deps.py`——在 `get_current_user` 成功返回前追加：

```python
    from app.core.request_context import set_user_id

    set_user_id(user_id)
```

（放在 `user_id` 校验通过、`get_user` 返回 `user` 之前或之后均可，建议紧邻返回前。）

`backend/app/api/errors.py`——修改 `unhandled_exception_handler`：

```python
    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        from app.core.request_context import get_request_context

        ctx = get_request_context()
        user_id = f" user_id={ctx.user_id}" if ctx and ctx.user_id else ""
        logger.exception("Unhandled error on %s %s%s", request.method, request.url.path, user_id)
        return _json(500, "服务器内部错误", "服务器内部错误")
```

- [ ] **Step 4: 运行确认通过**

```bash
cd backend && uv run pytest tests/test_request_context_integration.py -v
```
Expected: 2 passed

- [ ] **Step 5: 全量回归 + 提交**

```bash
cd backend && uv run pytest -q --tb=short
cd /Users/xiezhigang/Projects/me/zak2 && git add backend/app/api/deps.py backend/app/api/errors.py backend/tests/test_request_context_integration.py && git commit -m "$(cat <<'EOF'
feat(logging): 鉴权写入 user_id 并增强未捕获异常日志

get_current_user 成功后写入上下文；unhandled handler 附带
request_id/method/path/user_id，便于按请求排查。
EOF
)"
```

---

### Task 5: 文档 + 终验

**Files:**
- Modify: `backend/app/domains/README.md`（如合适补充横切说明）——或跳过
- Verify: 全量测试 + 手动 curl 冒烟

- [ ] **Step 1: 运行全量测试**

```bash
cd backend && uv run pytest -q --tb=short
```
Expected: 699 passed, 12 skipped（或 713 passed，取决于环境）

- [ ] **Step 2: import 冒烟**

```bash
cd backend && uv run python -c "import app.main; print('app.main ok')"
```

- [ ] **Step 3: 手动冒烟（可选，验证请求上下文真实生效）**

```bash
cd backend && uv run uvicorn app.main:app --port 8010 &
sleep 2
curl -i -H "X-Request-ID: manual-test" http://127.0.0.1:8010/health | head -5
kill %1
```
Expected: 响应头含 `X-Request-ID: manual-test`

- [ ] **Step 4: 提交**

```bash
cd /Users/xiezhigang/Projects/me/zak2 && git add -A && git commit -m "docs(backend): 补充 Phase 7 请求上下文说明" 2>/dev/null || echo "无文档变更，跳过"
```

---

## Spec coverage

| Spec 需求 | Tasks |
|-----------|-------|
| request_id 透传/生成/回显 | Task 1（规则）、Task 3（中间件） |
| 现有 logger 自动带 request_id | Task 2（Filter + logging 集成） |
| 未捕获异常日志增强 | Task 4 |
| 鉴权后 user_id 关联 | Task 4 |
| 不改业务语义 / 无新依赖 | Global Constraints，全程只动 5 处接入 |
| 测试覆盖（单元+集成+回归） | Task 1–4 + Task 5 全量 |

## Out of scope

- 访问日志（access log）中间件；JSON/结构化日志；ELK；OpenTelemetry
- ARQ 异步任务 request_id 传播（任务自带 job_id）
- 全库日志语句重写

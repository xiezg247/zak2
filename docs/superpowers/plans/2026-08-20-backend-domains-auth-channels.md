# 后端 Phase 0–1（domains auth/channels）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 落地 `domains/` 骨架与领域异常，并把 `auth`、`channels`（含 notify）迁入垂直切片，旧路径保留 thin re-export，对外 HTTP 行为不变。

**Architecture:** 横切留在 `core` / `api.deps` / `models`；业务进 `app.domains.{auth,channels}`。Router 只调 Service；Service 抛 `app.core.errors` 领域异常，由全局 handler 映射 HTTP。兼容壳保证既有 import / pytest patch 路径可逐步迁移。

**Tech Stack:** FastAPI、SQLAlchemy Session、Pydantic、pytest、现有 `ApiResponse` / `BaseRepository`。

**Spec:** [docs/superpowers/specs/2026-08-20-backend-architecture-refactor-design.md](../specs/2026-08-20-backend-architecture-refactor-design.md)

## Global Constraints

- 对外 REST 路径、JWT、Redis 键、ARQ job_id、渠道 schema 字段不变
- commit subject/body 简体中文，格式 `<type>(<scope>): <简述>`
- domain router **禁止** import / 实例化 `*Repository`
- domain **禁止** import `app.api.v1`
- `get_current_user` 留在 `app.api.deps`；`models` 不搬包
- 每个 Task 以可运行测试为门禁；优先小步提交

## File map（本计划结束时）

| 路径 | 职责 |
|------|------|
| `backend/app/domains/__init__.py` | 域包根 |
| `backend/app/domains/README.md` | 分层约定（Phase 0） |
| `backend/app/core/errors.py` | `AppError` 及子类 |
| `backend/app/api/errors.py` | 注册 `AppError` → HTTP |
| `backend/app/domains/auth/{login_guard,repository,schemas,service,router}.py` | auth 域 |
| `backend/app/domains/channels/{repository,schemas,service,router}.py` | channels 域 |
| `backend/app/domains/channels/notify/{feishu,delivery}.py` | 通知投递 |
| `backend/app/api/v1/auth.py` / `channels.py` | thin re-export router |
| `backend/app/services/login_guard.py` | re-export |
| `backend/app/repositories/{user,channel}.py` | re-export |
| `backend/app/schemas/{auth,channel}.py` | re-export |
| `backend/app/services/notify/*` | re-export |
| `docs/architecture-p1.md` | 结构行指向本 spec |

---

### Task 1: Phase 0 — `domains/` 骨架与约定

**Files:**
- Create: `backend/app/domains/__init__.py`
- Create: `backend/app/domains/auth/__init__.py`
- Create: `backend/app/domains/channels/__init__.py`
- Create: `backend/app/domains/channels/notify/__init__.py`
- Create: `backend/app/domains/README.md`

**Interfaces:**
- Produces: 可 `import app.domains`；约定文档与 spec 分层表一致

- [ ] **Step 1: 创建空包**

```python
# backend/app/domains/__init__.py
"""业务垂直切片根包（auth / channels / …）。"""

# backend/app/domains/auth/__init__.py
"""认证域。"""

# backend/app/domains/channels/__init__.py
"""消息渠道域。"""

# backend/app/domains/channels/notify/__init__.py
"""渠道投递（飞书 webhook 等）。"""
```

- [ ] **Step 2: 写入约定 README**

```markdown
# domains 约定

## 分层

| 层 | 可以依赖 | 禁止 |
|----|----------|------|
| router | service、schemas、`app.api.deps`、`ApiResponse` | repository、SQL、外部 HTTP |
| service | repository、`core`、`integrations`、其它域 service 公开 API | FastAPI `HTTPException` / `Request` |
| repository | `models`、`Session` | 业务规则、外部 IO |

## 兼容

迁移期间旧路径（`app.api.v1.*`、`app.repositories.*`、`app.services.notify`）仅允许 thin re-export。

详见 `docs/superpowers/specs/2026-08-20-backend-architecture-refactor-design.md`。
```

- [ ] **Step 3: 冒烟**

Run（在 `backend/`）:

```bash
uv run python -c "import app.domains; import app.domains.auth; import app.domains.channels.notify; print('ok')"
```

Expected: 打印 `ok`

- [ ] **Step 4: Commit**

```bash
git add backend/app/domains
git commit -m "$(cat <<'EOF'
refactor(backend): 新增 domains 包骨架与分层约定

为 auth/channels 垂直切片试点提供目录与导入基线。
EOF
)"
```

---

### Task 2: 领域异常 + 全局 handler

**Files:**
- Create: `backend/app/core/errors.py`
- Modify: `backend/app/api/errors.py`
- Create: `backend/tests/test_app_errors.py`
- Test（回归）: `backend/tests/test_error_handlers.py`

**Interfaces:**
- Produces:
  - `class AppError(Exception)`：属性 `message: str`、`status_code: int`、`detail: Any | None = None`
  - 子类：`NotFound` (404)、`ValidationFailed` (400)、`Unauthorized` (401)、`Forbidden` (403)、`RateLimited` (429)
  - handler：捕获 `AppError`，响应 body 与现有 `_json` 一致 `{code, message, detail, data}`

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_app_errors.py
from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.errors import register_exception_handlers
from app.core.errors import NotFound, RateLimited, ValidationFailed


def _client() -> TestClient:
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/nf")
    def nf() -> None:
        raise NotFound("渠道不存在")

    @app.get("/vf")
    def vf() -> None:
        raise ValidationFailed("没有需要更新的字段")

    @app.get("/rl")
    def rl() -> None:
        raise RateLimited("尝试次数过多，请稍后再试")

    return TestClient(app, raise_server_exceptions=False)


def test_not_found_maps_404() -> None:
    resp = _client().get("/nf")
    assert resp.status_code == 404
    body = resp.json()
    assert body["code"] == 404
    assert body["message"] == "渠道不存在"
    assert body["detail"] == "渠道不存在"
    assert body["data"] is None


def test_validation_failed_maps_400() -> None:
    resp = _client().get("/vf")
    assert resp.status_code == 400
    assert resp.json()["message"] == "没有需要更新的字段"


def test_rate_limited_maps_429() -> None:
    resp = _client().get("/rl")
    assert resp.status_code == 429
    assert "尝试次数过多" in resp.json()["message"]
```

- [ ] **Step 2: 跑测试确认失败**

```bash
cd backend && uv run pytest tests/test_app_errors.py -v
```

Expected: FAIL（`ModuleNotFoundError: app.core.errors` 或导入失败）

- [ ] **Step 3: 实现 `core/errors.py`**

```python
# backend/app/core/errors.py
"""领域异常：由 service 抛出，api/errors 映射为 HTTP JSON。"""

from __future__ import annotations

from typing import Any


class AppError(Exception):
    status_code: int = 500

    def __init__(self, message: str, *, detail: Any | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.detail = message if detail is None else detail


class NotFound(AppError):
    status_code = 404


class ValidationFailed(AppError):
    status_code = 400


class Unauthorized(AppError):
    status_code = 401


class Forbidden(AppError):
    status_code = 403


class RateLimited(AppError):
    status_code = 429
```

- [ ] **Step 4: 扩展 `register_exception_handlers`**

在 `backend/app/api/errors.py` 的 `register_exception_handlers` 内、`StarletteHTTPException` handler **之前**插入：

```python
from app.core.errors import AppError

@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    _ = request
    return _json(exc.status_code, exc.message, exc.detail)
```

保留现有 `StarletteHTTPException` / `RequestValidationError` / `Exception` handlers 不变。

- [ ] **Step 5: 跑测试确认通过**

```bash
cd backend && uv run pytest tests/test_app_errors.py tests/test_error_handlers.py -v
```

Expected: 全部 PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/core/errors.py backend/app/api/errors.py backend/tests/test_app_errors.py
git commit -m "$(cat <<'EOF'
feat(api): 引入 AppError 并由全局 handler 映射 HTTP

供 domains service 抛领域异常，避免 router 直接依赖 HTTPException。
EOF
)"
```

---

### Task 3: 迁入 `auth` 域

**Files:**
- Create: `backend/app/domains/auth/login_guard.py`（自 `services/login_guard.py` 原样搬入）
- Create: `backend/app/domains/auth/repository.py`（自 `repositories/user.py`）
- Create: `backend/app/domains/auth/schemas.py`（自 `schemas/auth.py`）
- Create: `backend/app/domains/auth/service.py`
- Create: `backend/app/domains/auth/router.py`
- Replace: `backend/app/services/login_guard.py` → re-export
- Replace: `backend/app/repositories/user.py` → re-export
- Replace: `backend/app/schemas/auth.py` → re-export
- Replace: `backend/app/api/v1/auth.py` → re-export `router`
- Modify: `backend/tests/test_login_guard.py`（改为 `from app.domains.auth import login_guard`）
- Create: `backend/tests/test_auth_service.py`
- Test（回归）: `backend/tests/test_auth_api.py`、`test_login_guard.py`、`test_security.py`

**Interfaces:**
- Consumes: `AppError` 子类；`create_access_token` / `verify_password`（`app.core.security`）
- Produces:
  - `AuthService.login(db, *, username: str, password: str, ip: str | None) -> TokenResponse`
  - 锁定 → `RateLimited`；密码错 → `Unauthorized`；禁用 → `Forbidden`
  - `router`：`APIRouter(prefix="/auth", tags=["auth"])`

- [ ] **Step 1: 写 AuthService 单元测试（先失败）**

```python
# backend/tests/test_auth_service.py
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.core.errors import Forbidden, RateLimited, Unauthorized
from app.core.security import hash_password
from app.domains.auth.service import AuthService


def test_login_success_returns_token() -> None:
    db = MagicMock()
    user = SimpleNamespace(
        id="u1",
        username="demo",
        display_name="Demo",
        password_hash=hash_password("demo-pass"),
        is_active=True,
    )
    with (
        patch("app.domains.auth.service.login_guard.is_locked", return_value=False),
        patch("app.domains.auth.service.login_guard.reset") as reset,
        patch("app.domains.auth.service.UserRepository") as Repo,
        patch("app.domains.auth.service.create_access_token", return_value="tok"),
    ):
        Repo.return_value.get_by_username.return_value = user
        out = AuthService.login(db, username="demo", password="demo-pass", ip="1.1.1.1")
    assert out.access_token == "tok"
    assert out.user.username == "demo"
    reset.assert_called_once()


def test_login_locked_raises_rate_limited() -> None:
    db = MagicMock()
    with patch("app.domains.auth.service.login_guard.is_locked", return_value=True):
        with pytest.raises(RateLimited):
            AuthService.login(db, username="demo", password="x", ip=None)


def test_login_bad_password_raises_unauthorized() -> None:
    db = MagicMock()
    user = SimpleNamespace(
        id="u1",
        username="demo",
        display_name="Demo",
        password_hash=hash_password("demo-pass"),
        is_active=True,
    )
    with (
        patch("app.domains.auth.service.login_guard.is_locked", return_value=False),
        patch("app.domains.auth.service.login_guard.record_failure") as fail,
        patch("app.domains.auth.service.UserRepository") as Repo,
    ):
        Repo.return_value.get_by_username.return_value = user
        with pytest.raises(Unauthorized):
            AuthService.login(db, username="demo", password="wrong", ip="1.1.1.1")
    fail.assert_called_once()


def test_login_disabled_raises_forbidden() -> None:
    db = MagicMock()
    user = SimpleNamespace(
        id="u1",
        username="demo",
        display_name="Demo",
        password_hash=hash_password("demo-pass"),
        is_active=False,
    )
    with (
        patch("app.domains.auth.service.login_guard.is_locked", return_value=False),
        patch("app.domains.auth.service.UserRepository") as Repo,
    ):
        Repo.return_value.get_by_username.return_value = user
        with pytest.raises(Forbidden):
            AuthService.login(db, username="demo", password="demo-pass", ip=None)
```

- [ ] **Step 2: 跑测试确认失败**

```bash
cd backend && uv run pytest tests/test_auth_service.py -v
```

Expected: FAIL（`AuthService` 不存在）

- [ ] **Step 3: 搬迁 login_guard / repository / schemas**

1. 将 `backend/app/services/login_guard.py` **文件内容原样**写入 `backend/app/domains/auth/login_guard.py`
2. 将 `backend/app/repositories/user.py` 原样写入 `backend/app/domains/auth/repository.py`（类名仍为 `UserRepository`）
3. 将 `backend/app/schemas/auth.py` 原样写入 `backend/app/domains/auth/schemas.py`
4. 把旧三处改为 re-export：

```python
# backend/app/services/login_guard.py
"""兼容壳：实现已迁至 app.domains.auth.login_guard。"""
from app.domains.auth.login_guard import *  # noqa: F403
from app.domains.auth.login_guard import is_locked, record_failure, reset

__all__ = ["is_locked", "record_failure", "reset"]

# backend/app/repositories/user.py
"""兼容壳：实现已迁至 app.domains.auth.repository。"""
from app.domains.auth.repository import UserRepository

__all__ = ["UserRepository"]

# backend/app/schemas/auth.py
"""兼容壳：实现已迁至 app.domains.auth.schemas。"""
from app.domains.auth.schemas import LoginRequest, TokenResponse, UserOut

__all__ = ["LoginRequest", "TokenResponse", "UserOut"]
```

注意：`test_login_guard.py` 使用 `patch.object(login_guard, "_client")`，必须改为：

```python
from app.domains.auth import login_guard
```

否则 patch 打在兼容壳上，域内函数看不到。

- [ ] **Step 4: 实现 AuthService**

```python
# backend/app/domains/auth/service.py
from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.errors import Forbidden, RateLimited, Unauthorized
from app.core.security import create_access_token, verify_password
from app.domains.auth import login_guard
from app.domains.auth.repository import UserRepository
from app.domains.auth.schemas import TokenResponse, UserOut


class AuthService:
    @staticmethod
    def login(db: Session, *, username: str, password: str, ip: str | None) -> TokenResponse:
        if login_guard.is_locked(username, ip):
            raise RateLimited("尝试次数过多，请稍后再试")
        user = UserRepository(db).get_by_username(username)
        if user is None or not verify_password(password, user.password_hash):
            login_guard.record_failure(username, ip)
            raise Unauthorized("用户名或密码错误")
        if not user.is_active:
            raise Forbidden("用户已禁用")
        login_guard.reset(username, ip)
        token = create_access_token(user_id=str(user.id), username=user.username)
        return TokenResponse(
            access_token=token,
            user=UserOut(id=str(user.id), username=user.username, display_name=user.display_name),
        )
```

- [ ] **Step 5: 实现 auth router（薄）**

```python
# backend/app/domains/auth/router.py
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.db import get_db
from app.domains.auth.schemas import LoginRequest, TokenResponse, UserOut
from app.domains.auth.service import AuthService
from app.models.user import User
from app.schemas.common import ApiResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=ApiResponse[TokenResponse])
def login(body: LoginRequest, request: Request, db: Session = Depends(get_db)) -> ApiResponse[TokenResponse]:
    ip = request.client.host if request.client else None
    data = AuthService.login(db, username=body.username, password=body.password, ip=ip)
    return ApiResponse(data=data)


@router.get("/me", response_model=ApiResponse[UserOut])
def me(user: User = Depends(get_current_user)) -> ApiResponse[UserOut]:
    return ApiResponse(data=UserOut(id=str(user.id), username=user.username, display_name=user.display_name))
```

- [ ] **Step 6: `api/v1/auth.py` 改为 re-export**

```python
# backend/app/api/v1/auth.py
"""兼容壳：路由实现已迁至 app.domains.auth.router。"""
from app.domains.auth.router import router

__all__ = ["router"]
```

确认 `app/api/v1/__init__.py` 仍 `include_router(auth.router)`，无需改。

- [ ] **Step 7: 跑测试**

```bash
cd backend && uv run pytest tests/test_auth_service.py tests/test_login_guard.py tests/test_auth_api.py tests/test_security.py tests/test_error_handlers.py -v
```

Expected: 全部 PASS

- [ ] **Step 8: 分层断言**

```bash
cd backend && rg "Repository" app/domains/auth/router.py && echo "FAIL: router mentions Repository" && exit 1 || echo "ok"
```

Expected: 打印 `ok`

- [ ] **Step 9: Commit**

```bash
git add backend/app/domains/auth backend/app/api/v1/auth.py backend/app/services/login_guard.py \
  backend/app/repositories/user.py backend/app/schemas/auth.py \
  backend/tests/test_auth_service.py backend/tests/test_login_guard.py
git commit -m "$(cat <<'EOF'
refactor(auth): 登录域迁入 domains 并由 AuthService 承接

API 变薄；旧 repositories/schemas/login_guard 路径保留兼容壳。
EOF
)"
```

---

### Task 4: 迁入 `channels` 域（含 notify）

**Files:**
- Create: `backend/app/domains/channels/notify/feishu.py`（自 `services/notify/feishu.py`）
- Create: `backend/app/domains/channels/notify/delivery.py`（自 `services/notify/delivery.py`，内部改为域内 feishu import）
- Create: `backend/app/domains/channels/repository.py`（自 `repositories/channel.py`，`ChannelOut` 改为域内 schemas）
- Create: `backend/app/domains/channels/schemas.py`（自 `schemas/channel.py`）
- Create: `backend/app/domains/channels/service.py`
- Create: `backend/app/domains/channels/router.py`
- Replace: `backend/app/services/notify/feishu.py`、`delivery.py` → re-export
- Replace: `backend/app/repositories/channel.py`、`backend/app/schemas/channel.py`、`backend/app/api/v1/channels.py` → re-export
- Modify: `backend/tests/test_notify_feishu.py`、`test_notify_delivery.py` 的 **patch 目标**改为 `app.domains.channels.notify.*`
- Create: `backend/tests/test_channel_service.py`
- Test（回归）: `backend/tests/test_channels_api.py`、`test_notify_*.py`

**Interfaces:**
- Consumes: `NotFound`、`ValidationFailed`；`send_to_channel` / `deliver_text`
- Produces:
  - `ChannelService.list_channels(db, user_id) -> ChannelListOut`
  - `ChannelService.create_channel(db, user_id, body: ChannelCreate) -> ChannelOut`
  - `ChannelService.update_channel(db, user_id, channel_id, body: ChannelUpdate) -> ChannelOut`
  - `ChannelService.delete_channel(db, user_id, channel_id) -> None`
  - `ChannelService.test_channel(db, user_id, channel_id) -> ChannelTestOut`
  - 空更新 → `ValidationFailed`；缺失渠道 → `NotFound`

- [ ] **Step 1: 写 ChannelService 失败测试**

```python
# backend/tests/test_channel_service.py
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.core.errors import NotFound, ValidationFailed
from app.domains.channels.schemas import ChannelCreate, ChannelUpdate
from app.domains.channels.service import ChannelService


def test_update_empty_raises_validation() -> None:
    db = MagicMock()
    with pytest.raises(ValidationFailed):
        ChannelService.update_channel(db, "u1", "c1", ChannelUpdate())


def test_get_missing_raises_not_found() -> None:
    db = MagicMock()
    with patch("app.domains.channels.service.ChannelRepository") as Repo:
        Repo.return_value.get.return_value = None
        with pytest.raises(NotFound):
            ChannelService.delete_channel(db, "u1", "missing")


def test_test_channel_ok_message() -> None:
    db = MagicMock()
    channel = SimpleNamespace(id="c1", name="组群")
    with (
        patch("app.domains.channels.service.ChannelRepository") as Repo,
        patch(
            "app.domains.channels.service.notify_delivery.send_to_channel",
            return_value=(True, ""),
        ),
    ):
        Repo.return_value.get.return_value = channel
        out = ChannelService.test_channel(db, "u1", "c1")
    assert out.ok is True
    assert "成功" in out.message
```

- [ ] **Step 2: 跑测试确认失败**

```bash
cd backend && uv run pytest tests/test_channel_service.py -v
```

Expected: FAIL

- [ ] **Step 3: 搬迁 notify + repository + schemas**

1. `feishu.py` 原样 → `domains/channels/notify/feishu.py`
2. `delivery.py` 复制到 `domains/channels/notify/delivery.py`，仅改 import：

```python
from app.domains.channels.notify.feishu import FeishuSendError, send_feishu_webhook
```

3. `schemas/channel.py` → `domains/channels/schemas.py`
4. `repositories/channel.py` → `domains/channels/repository.py`，并改：

```python
from app.domains.channels.schemas import ChannelOut
from app.repositories.base import BaseRepository
```

5. 兼容壳：

```python
# backend/app/services/notify/feishu.py
from app.domains.channels.notify.feishu import FeishuSendError, send_feishu_webhook

__all__ = ["FeishuSendError", "send_feishu_webhook"]

# backend/app/services/notify/delivery.py
from app.domains.channels.notify.delivery import deliver_text, send_to_channel

__all__ = ["deliver_text", "send_to_channel"]

# backend/app/repositories/channel.py
from app.domains.channels.repository import ChannelRepository

__all__ = ["ChannelRepository"]

# backend/app/schemas/channel.py
from app.domains.channels.schemas import (
    ChannelCreate,
    ChannelListOut,
    ChannelOut,
    ChannelTestOut,
    ChannelUpdate,
)

__all__ = [
    "ChannelCreate",
    "ChannelListOut",
    "ChannelOut",
    "ChannelTestOut",
    "ChannelUpdate",
]
```

6. 更新测试 patch 字符串：

- `test_notify_feishu.py`：`app.services.notify.feishu.httpx.post` → `app.domains.channels.notify.feishu.httpx.post`
- `test_notify_delivery.py`：`app.services.notify.delivery.send_feishu_webhook` → `app.domains.channels.notify.delivery.send_feishu_webhook`；`app.services.notify.delivery.send_to_channel` → `app.domains.channels.notify.delivery.send_to_channel`

`ops/auto_screen.py`、`ops/auto_schedule.py` 可暂时继续 `from app.services.notify import delivery`（兼容壳）。

- [ ] **Step 4: 实现 ChannelService**

```python
# backend/app/domains/channels/service.py
from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.errors import NotFound, ValidationFailed
from app.domains.channels.notify import delivery as notify_delivery
from app.domains.channels.repository import ChannelRepository
from app.domains.channels.schemas import (
    ChannelCreate,
    ChannelListOut,
    ChannelOut,
    ChannelTestOut,
    ChannelUpdate,
)


class ChannelService:
    @staticmethod
    def list_channels(db: Session, user_id: str) -> ChannelListOut:
        repo = ChannelRepository(db, user_id)
        return ChannelListOut(items=[repo.to_out(ch) for ch in repo.list_all()])

    @staticmethod
    def create_channel(db: Session, user_id: str, body: ChannelCreate) -> ChannelOut:
        repo = ChannelRepository(db, user_id)
        channel = repo.create_channel(
            name=body.name.strip(),
            webhook_url=body.webhook_url.strip(),
            enabled=body.enabled,
        )
        return repo.to_out(channel)

    @staticmethod
    def update_channel(
        db: Session, user_id: str, channel_id: str, body: ChannelUpdate
    ) -> ChannelOut:
        values = body.model_dump(exclude_none=True)
        if not values:
            raise ValidationFailed("没有需要更新的字段")
        if "name" in values:
            values["name"] = str(values["name"]).strip()
        if "webhook_url" in values:
            values["webhook_url"] = str(values["webhook_url"]).strip()
        repo = ChannelRepository(db, user_id)
        if repo.get(channel_id) is None:
            raise NotFound("渠道不存在")
        channel = repo.update_channel(channel_id, values)
        if channel is None:
            raise NotFound("渠道不存在")
        return repo.to_out(channel)

    @staticmethod
    def delete_channel(db: Session, user_id: str, channel_id: str) -> None:
        repo = ChannelRepository(db, user_id)
        if repo.get(channel_id) is None:
            raise NotFound("渠道不存在")
        repo.delete(channel_id)

    @staticmethod
    def test_channel(db: Session, user_id: str, channel_id: str) -> ChannelTestOut:
        repo = ChannelRepository(db, user_id)
        channel = repo.get(channel_id)
        if channel is None:
            raise NotFound("渠道不存在")
        ok, message = notify_delivery.send_to_channel(
            db,
            channel,
            event_type="channel.test",
            title="消息渠道测试",
            text="这是一条测试消息：zak2 消息渠道已成功接入飞书。",
        )
        return ChannelTestOut(ok=ok, message=message if not ok else "测试消息发送成功")
```

- [ ] **Step 5: 实现 channels router**

```python
# backend/app/domains/channels/router.py
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.db import get_db
from app.domains.channels.schemas import (
    ChannelCreate,
    ChannelListOut,
    ChannelOut,
    ChannelTestOut,
    ChannelUpdate,
)
from app.domains.channels.service import ChannelService
from app.models.user import User
from app.schemas.common import ApiResponse, OkOut

router = APIRouter(prefix="/channels", tags=["channels"])


@router.get("", response_model=ApiResponse[ChannelListOut])
def list_channels(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[ChannelListOut]:
    return ApiResponse(data=ChannelService.list_channels(db, str(user.id)))


@router.post("", response_model=ApiResponse[ChannelOut])
def create_channel(
    body: ChannelCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[ChannelOut]:
    return ApiResponse(data=ChannelService.create_channel(db, str(user.id), body))


@router.patch("/{channel_id}", response_model=ApiResponse[ChannelOut])
def update_channel(
    channel_id: str,
    body: ChannelUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[ChannelOut]:
    return ApiResponse(
        data=ChannelService.update_channel(db, str(user.id), channel_id, body)
    )


@router.delete("/{channel_id}", response_model=ApiResponse[OkOut])
def delete_channel(
    channel_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[OkOut]:
    ChannelService.delete_channel(db, str(user.id), channel_id)
    return ApiResponse(data=OkOut())


@router.post("/{channel_id}/test", response_model=ApiResponse[ChannelTestOut])
def test_channel(
    channel_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiResponse[ChannelTestOut]:
    return ApiResponse(data=ChannelService.test_channel(db, str(user.id), channel_id))
```

- [ ] **Step 6: `api/v1/channels.py` re-export**

```python
# backend/app/api/v1/channels.py
"""兼容壳：路由实现已迁至 app.domains.channels.router。"""
from app.domains.channels.router import router

__all__ = ["router"]
```

- [ ] **Step 7: 跑测试**

```bash
cd backend && uv run pytest \
  tests/test_channel_service.py \
  tests/test_channels_api.py \
  tests/test_notify_feishu.py \
  tests/test_notify_delivery.py \
  tests/test_auth_service.py \
  tests/test_auth_api.py \
  tests/test_app_errors.py -v
```

Expected: 全部 PASS

- [ ] **Step 8: router 分层检查**

```bash
cd backend && (rg "Repository" app/domains/channels/router.py && exit 1 || echo ok)
```

Expected: `ok`

- [ ] **Step 9: Commit**

```bash
git add backend/app/domains/channels backend/app/api/v1/channels.py \
  backend/app/services/notify backend/app/repositories/channel.py backend/app/schemas/channel.py \
  backend/tests/test_channel_service.py backend/tests/test_notify_feishu.py backend/tests/test_notify_delivery.py
git commit -m "$(cat <<'EOF'
refactor(channels): 渠道与 notify 迁入 domains 并由 ChannelService 承接

CRUD/测试发送离开 router；旧 notify/repository/schemas 路径保留兼容壳。
EOF
)"
```

---

### Task 5: 文档指针 + 全量相关回归

**Files:**
- Modify: `docs/architecture-p1.md`（结构行）

**Interfaces:**
- Produces: architecture 文档指向新总纲；Phase 0–1 验收命令绿

- [ ] **Step 1: 更新 architecture 结构说明**

将 `docs/architecture-p1.md` 决策表中「结构」一行改为：

```markdown
| 结构 | `backend/` FastAPI + `frontend/` Vue3；后端业务域渐进迁入 `app/domains/`（见 [backend-architecture-refactor-design](./superpowers/specs/2026-08-20-backend-architecture-refactor-design.md)） |
```

- [ ] **Step 2: 全量相关回归**

```bash
cd backend && uv run pytest \
  tests/test_app_errors.py \
  tests/test_error_handlers.py \
  tests/test_auth_service.py \
  tests/test_auth_api.py \
  tests/test_login_guard.py \
  tests/test_security.py \
  tests/test_channel_service.py \
  tests/test_channels_api.py \
  tests/test_notify_feishu.py \
  tests/test_notify_delivery.py -v
```

Expected: 全部 PASS

- [ ] **Step 3: Commit**

```bash
git add docs/architecture-p1.md
git commit -m "$(cat <<'EOF'
docs(architecture): 标注 backend domains 渐进重构入口

指向混合垂直切片总纲，避免结构描述与代码演进脱节。
EOF
)"
```

---

## Spec coverage checklist

| Spec 项 | Task |
|---------|------|
| Phase 0 domains 骨架 + 约定 | Task 1 |
| `core/errors` + handler | Task 2 |
| auth 迁入 + AuthService + 兼容壳 | Task 3 |
| channels + notify 迁入 + ChannelService + 兼容壳 | Task 4 |
| architecture-p1 结构行指针 | Task 5 |
| route 不直连 repository | Task 3/4 Step 8 |
| HTTP / schema 兼容 | 既有 API 测试回归 |
| models 不搬 | 全计划未改 models 包 |

## Out of scope（本 plan 不做）

- Phase 2+ 其它域迁移
- 拆除兼容壳（Phase 6）
- 拆 `ai_tools` / `watchlist` 大文件
- 改前端

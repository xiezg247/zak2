# 消息渠道（飞书接入）实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Web 端新增「消息渠道」菜单，用户填写飞书自定义机器人 Webhook 完成接入，选股/盘后结果推送到已接入渠道并写入投递日志。

**Architecture:** 新表 `app.notify_channel` 存渠道配置（按用户隔离）；`services/notify/feishu.py` 负责 webhook 发送，`services/notify/delivery.py` 负责遍历渠道发送 + 写 `notify_delivery_log`；`api/v1/channels.py` 提供 CRUD + test；`ops/auto_screen.py` 选股成功后调用推送（失败不影响主流程）。

**Tech Stack:** FastAPI + SQLAlchemy + alembic + httpx；Vue3 + TypeScript。

## Global Constraints

- 语言：代码注释/字符串用中文；commit subject 与 body 用简体中文，格式 `<type>(<scope>): <简述>`
- 后端遵循既有工程模式：`BaseRepository(db, user_id)` 构造约定、`ApiResponse` 统一包裹、`get_current_user` 鉴权
- 前端遵循既有模式：`api<T>(path, options)` 客户端、`AppShell` 布局、`NavIcon` 图标表、scoped CSS
- 推送失败绝不抛异常影响选股主流程（只写投递日志）
- commit 频繁且独立可测试

---

### Task 1: NotifyChannel 模型 + alembic 迁移

**Files:**
- Create: `backend/app/models/channel.py`
- Modify: `backend/app/models/__init__.py`
- Create: `backend/alembic/versions/012_notify_channel.py`

**Interfaces:**
- Produces: `NotifyChannel` 模型，字段 `id / user_id / channel_type / name / config_json / enabled / created_at / updated_at`（前两个为 UUID，`config_json` Text 存 `{"webhook_url": "..."}`，时间戳为 Text `YYYY-MM-DD HH:MM:SS`）

- [ ] **Step 1: 创建模型**

```python
# backend/app/models/channel.py
from __future__ import annotations

from sqlalchemy import Boolean, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class NotifyChannel(Base):
    """消息推送渠道（app.notify_channel）。"""

    __tablename__ = "notify_channel"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True)
    user_id: Mapped[str] = mapped_column(UUID(as_uuid=False), nullable=False, index=True)
    channel_type: Mapped[str] = mapped_column(Text, nullable=False, default="feishu")
    name: Mapped[str] = mapped_column(Text, nullable=False)
    config_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False)
```

- [ ] **Step 2: 注册模型**（`models/__init__.py` 加 import 与 `__all__` 项）

- [ ] **Step 3: 创建迁移**（仿 `007_web_team_reports.py`，revision `012_notify_channel`，down_revision `011_drop_trading_plans`）

```python
# backend/alembic/versions/012_notify_channel.py
def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS app.notify_channel (
          id uuid PRIMARY KEY,
          user_id uuid NOT NULL,
          channel_type text NOT NULL DEFAULT 'feishu',
          name text NOT NULL,
          config_json text NOT NULL DEFAULT '{}',
          enabled boolean NOT NULL DEFAULT TRUE,
          created_at text NOT NULL,
          updated_at text NOT NULL
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_notify_channel_user ON app.notify_channel (user_id)")

def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS app.notify_channel")
```

- [ ] **Step 4: 冒烟验证**：`python -c "from app.models import NotifyChannel; print(NotifyChannel.__tablename__)"`（在 backend 目录）

- [ ] **Step 5: Commit**

---

### Task 2: 飞书 webhook 发送服务

**Files:**
- Create: `backend/app/services/notify/__init__.py`（空包）
- Create: `backend/app/services/notify/feishu.py`
- Test: `backend/tests/test_notify_feishu.py`

**Interfaces:**
- Produces: `send_feishu_webhook(webhook_url: str, title: str, text: str) -> None`；失败抛 `FeishuSendError(message)`。payload 用 `msg_type: interactive` + card（header title + lark_md element）

- [ ] **Step 1: 写测试**（mock `httpx.post`）

```python
# backend/tests/test_notify_feishu.py
from unittest.mock import MagicMock, patch

import pytest

from app.services.notify.feishu import FeishuSendError, send_feishu_webhook


def test_send_ok():
    with patch("app.services.notify.feishu.httpx.post", return_value=MagicMock(status_code=200, json=lambda: {"code": 0, "msg": "success"})) as post:
        send_feishu_webhook("https://hook", "标题", "正文")
    post.assert_called_once()
    payload = post.call_args.kwargs["json"]
    assert payload["msg_type"] == "interactive"


def test_send_http_error():
    with patch("app.services.notify.feishu.httpx.post", side_effect=Exception("boom")):
        with pytest.raises(FeishuSendError):
            send_feishu_webhook("https://hook", "标题", "正文")


def test_send_feishu_code_error():
    with patch("app.services.notify.feishu.httpx.post", return_value=MagicMock(status_code=200, json=lambda: {"code": 19001, "msg": "bad"})):
        with pytest.raises(FeishuSendError):
            send_feishu_webhook("https://hook", "标题", "正文")


def test_send_non_200():
    with patch("app.services.notify.feishu.httpx.post", return_value=MagicMock(status_code=500, text="err")):
        with pytest.raises(FeishuSendError):
            send_feishu_webhook("https://hook", "标题", "正文")
```

- [ ] **Step 2: 实现**（httpx 10s 超时；`HTTPError` → 网络错误；`status_code>=400` → HTTP 错误；非 JSON → 解析失败；`code!=0` → 飞书错误）

```python
# backend/app/services/notify/feishu.py
from __future__ import annotations

import httpx

FEISHU_WEBHOOK_TIMEOUT_S = 10.0


class FeishuSendError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


def send_feishu_webhook(webhook_url: str, title: str, text: str) -> None:
    payload = {
        "msg_type": "interactive",
        "card": {
            "header": {"title": {"tag": "plain_text", "content": title}},
            "elements": [{"tag": "div", "text": {"tag": "lark_md", "content": text}}],
        },
    }
    try:
        resp = httpx.post(webhook_url, json=payload, timeout=FEISHU_WEBHOOK_TIMEOUT_S)
    except httpx.HTTPError as exc:
        raise FeishuSendError(f"网络错误：{exc}") from exc
    if resp.status_code >= 400:
        raise FeishuSendError(f"HTTP {resp.status_code}：{(resp.text or '')[:200]}")
    try:
        data = resp.json()
    except ValueError as exc:
        raise FeishuSendError(f"响应解析失败：{(resp.text or '')[:200]}") from exc
    if data.get("code") != 0:
        raise FeishuSendError(f"飞书返回错误：{data.get('msg') or data}")
```

- [ ] **Step 3: 跑测试**：`pytest tests/test_notify_feishu.py -v`（backend 目录，venv）→ 4 passed
- [ ] **Step 4: Commit**

---

### Task 3: 投递服务（遍历渠道发送 + 写日志）

**Files:**
- Create: `backend/app/services/notify/delivery.py`
- Test: `backend/tests/test_notify_delivery.py`

**Interfaces:**
- Consumes: `NotifyChannel`、`send_feishu_webhook` / `FeishuSendError`、`NotifyDeliveryLog`
- Produces:
  - `send_to_channel(db, channel, *, event_type, title, text) -> tuple[bool, str]`：单渠道发送 + 写投递日志，返回 `(ok, error_message)`
  - `deliver_text(db, *, user_id, event_type, title, text) -> dict`：查该用户启用渠道，逐个发送；永不抛异常；返回 `{"sent": n, "failed": n, "errors": [...]}`
  - `_now_str() -> str`：`YYYY-MM-DD HH:MM:SS`（UTC）

- [ ] **Step 1: 写测试**

```python
# backend/tests/test_notify_delivery.py
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.services.notify.delivery import deliver_text, send_to_channel
from app.services.notify.feishu import FeishuSendError


def test_send_to_channel_ok():
    db = MagicMock()
    ch = SimpleNamespace(id="c1", user_id="u1", channel_type="feishu", name="组群", config_json='{"webhook_url":"https://hook"}')
    with patch("app.services.notify.delivery.send_feishu_webhook") as send:
        ok, msg = send_to_channel(db, ch, event_type="ops.screen", title="t", text="x")
    assert ok is True and msg == ""
    assert db.add.called and db.commit.called
    row = db.add.call_args.args[0]
    assert row.channel == "feishu"
    assert row.status == "ok"


def test_send_to_channel_error_logged():
    db = MagicMock()
    ch = SimpleNamespace(id="c1", user_id="u1", channel_type="feishu", name="组群", config_json='{"webhook_url":"https://hook"}')
    with patch("app.services.notify.delivery.send_feishu_webhook", side_effect=FeishuSendError("HTTP 500")):
        ok, msg = send_to_channel(db, ch, event_type="ops.screen", title="t", text="x")
    assert ok is False and msg == "HTTP 500"
    row = db.add.call_args.args[0]
    assert row.status == "error"
    assert row.error == "HTTP 500"


def test_deliver_text_skips_when_no_channels():
    db = MagicMock()
    db.scalars.return_value = []
    out = deliver_text(db, user_id="u1", event_type="e", title="t", text="x")
    assert out == {"sent": 0, "failed": 0, "errors": []}


def test_deliver_text_counts_mixed():
    db = MagicMock()
    db.scalars.return_value = [
        SimpleNamespace(id="c1", user_id="u1", channel_type="feishu", name="a", config_json='{"webhook_url":"https://a"}'),
        SimpleNamespace(id="c2", user_id="u1", channel_type="feishu", name="b", config_json='{"webhook_url":"https://b"}'),
    ]
    with patch(
        "app.services.notify.delivery.send_to_channel",
        side_effect=[(True, ""), (False, "HTTP 500")],
    ):
        out = deliver_text(db, user_id="u1", event_type="e", title="t", text="x")
    assert out["sent"] == 1 and out["failed"] == 1
    assert out["errors"] == [{"channel_id": "c2", "message": "HTTP 500"}]
```

- [ ] **Step 2: 实现**（`deliver_text` 查 `select(NotifyChannel).where(user_id==, enabled.is_(True))`；`send_to_channel` 解析 config_json 取 webhook_url、调用发送、写 `NotifyDeliveryLog` 并 commit；`created_at` 用 `_now_str()`）

```python
# backend/app/services/notify/delivery.py
from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.channel import NotifyChannel
from app.models.notify import NotifyDeliveryLog
from app.services.notify.feishu import FeishuSendError, send_feishu_webhook


def _now_str() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")


def _webhook_of(channel: NotifyChannel) -> str:
    try:
        cfg = json.loads(channel.config_json or "{}")
        return str(cfg.get("webhook_url") or "")
    except (json.JSONDecodeError, TypeError):
        return ""


def send_to_channel(
    db: Session,
    channel: NotifyChannel,
    *,
    event_type: str,
    title: str,
    text: str,
) -> tuple[bool, str]:
    webhook_url = _webhook_of(channel)
    if not webhook_url:
        status, error = "error", "渠道缺少 webhook_url"
    else:
        try:
            send_feishu_webhook(webhook_url, title, text)
            status, error = "ok", ""
        except FeishuSendError as exc:
            status, error = "error", exc.message
    db.add(
        NotifyDeliveryLog(
            id=str(uuid4()),
            user_id=channel.user_id,
            event_type=event_type,
            channel=channel.channel_type,
            payload_json=json.dumps({"channel_id": channel.id, "channel_name": channel.name, "title": title}, ensure_ascii=False),
            status=status,
            error=error,
            created_at=_now_str(),
        )
    )
    db.commit()
    return status == "ok", error


def deliver_text(
    db: Session,
    *,
    user_id: str,
    event_type: str,
    title: str,
    text: str,
) -> dict[str, Any]:
    channels = list(
        db.scalars(
            select(NotifyChannel).where(
                NotifyChannel.user_id == user_id,
                NotifyChannel.enabled.is_(True),
            )
        )
    )
    sent, failed = 0, 0
    errors: list[dict[str, str]] = []
    for channel in channels:
        ok, message = send_to_channel(
            db,
            channel,
            event_type=event_type,
            title=title,
            text=text,
        )
        if ok:
            sent += 1
        else:
            failed += 1
            errors.append({"channel_id": channel.id, "message": message})
    return {"sent": sent, "failed": failed, "errors": errors}
```

- [ ] **Step 3: 跑测试**：`pytest tests/test_notify_delivery.py -v` → 4 passed
- [ ] **Step 4: Commit**

---

### Task 4: channels API（CRUD + test）

**Files:**
- Create: `backend/app/schemas/channel.py`
- Create: `backend/app/repositories/channel.py`
- Create: `backend/app/api/v1/channels.py`
- Modify: `backend/app/api/v1/__init__.py`
- Test: `backend/tests/test_channels_api.py`

**Interfaces:**
- Consumes: `BaseRepository`、`send_to_channel`、`get_current_user`、`ApiResponse`
- Produces:
  - schemas: `ChannelOut(id, channel_type, name, webhook_url, enabled, created_at, updated_at)`、`ChannelCreate(channel_type='feishu', name, webhook_url, enabled=True)`、`ChannelUpdate(name|None, webhook_url|None, enabled|None)`、`ChannelListOut(items)`、`ChannelTestOut(ok, message)`
  - `ChannelRepository(BaseRepository)`：`model = NotifyChannel`，覆写 `create` 填充 config_json / 时间戳；`update` 支持局部更新；`to_out(channel)` 转换
  - API（`/api/v1` 前缀，router 无 prefix）：
    - `GET /channels` → `ApiResponse[ChannelListOut]`
    - `POST /channels` → `ApiResponse[ChannelOut]`（400：name/webhook_url 缺失）
    - `PATCH /channels/{channel_id}` → `ApiResponse[ChannelOut]`（404：不存在/非本人）
    - `DELETE /channels/{channel_id}` → `ApiResponse[OkOut]`（404 同上）
    - `POST /channels/{channel_id}/test` → `ApiResponse[ChannelTestOut]`（实际发送测试消息，返回 ok/message）

- [ ] **Step 1: 写 schema 与 repository**
- [ ] **Step 2: 写 API 路由**（仿 watchlist.py 的依赖注入写法）并注册进 `api_router`
- [ ] **Step 3: 写测试**（仿 `test_notify_log.py` 的 `_api_client` 模式：`TestClient(create_app())` + dependency_overrides；`ChannelRepository` 用 MagicMock 返回预构造对象）

```python
# backend/tests/test_channels_api.py 关键用例
def test_list_channels_empty():  # GET /api/v1/channels → data.items == []
def test_create_channel_valid():  # POST /channels 提交 name+webhook_url → 201/200 + ChannelOut
def test_create_channel_missing_name():  # → 422（pydantic 校验）
def test_update_channel():  # PATCH → 返回更新后对象
def test_delete_channel():  # DELETE → OkOut
def test_delete_missing_404():  # repo.get 返回 None → 404
def test_test_channel_ok():  # mock send_to_channel → (True, "") → ChannelTestOut(ok=True)
```

- [ ] **Step 4: 跑测试**：`pytest tests/test_channels_api.py -v` → 全部通过
- [ ] **Step 5: Commit**

---

### Task 5: 选股/盘后结果推送集成

**Files:**
- Modify: `backend/app/services/ops/auto_screen.py`
- Test: `backend/tests/test_ops_auto_screen.py`（追加用例）

**Interfaces:**
- Consumes: `deliver_text`、`result` 里的 `rows`（list[dict] 含 `symbol/name/change_pct`）
- Produces: `_format_screen_lines(label, result, run_id) -> str`（选股 Top 列表文本，供复用）

- [ ] **Step 1: 追加测试**

```python
def test_screen_intraday_delivers_notification():
    db = MagicMock()
    fake_result = {
        "condition": "盘中多因子", "source": "recipe", "row_count": 1, "total_scanned": 10,
        "config": {},
        "rows": [{"symbol": "600519", "name": "贵州茅台", "change_pct": 2.31}],
    }
    fake_run = MagicMock(id="run-1")
    with (
        patch("app.services.ops.auto_screen.load_scheduler_config", return_value=SchedulerConfigOut(id="default", config={})),
        patch("app.repositories.screener.ScreenerRunRepository.latest_run_symbols", return_value=None),
        patch("app.services.ops.auto_screen.run_recipe_screen", return_value=fake_result),
        patch("app.repositories.screener.ScreenerRunRepository.save_run", return_value=fake_run),
        patch("app.services.ops.auto_screen.save_job_run_meta"),
        patch("app.services.ops.auto_screen.notify_delivery.deliver_text") as deliver,
    ):
        out = screen_intraday(db, user_id="u1")
    assert out.success is True
    deliver.assert_called_once()
    kwargs = deliver.call_args.kwargs
    assert kwargs["user_id"] == "u1"
    assert kwargs["event_type"] == "ops.screen_intraday"
    assert "贵州茅台" in kwargs["text"]


def test_screen_post_close_deliver_failure_does_not_raise():
    db = MagicMock()
    fake_result = {"condition": "盘后多因子", "source": "recipe", "row_count": 0, "total_scanned": 20, "config": {}, "rows": []}
    fake_run = MagicMock(id="run-pc")
    with (
        patch("app.services.ops.auto_screen.load_scheduler_config", return_value=SchedulerConfigOut(id="default", config={})),
        patch("app.repositories.screener.ScreenerRunRepository.latest_run_symbols", return_value=None),
        patch("app.services.ops.auto_screen.run_recipe_screen", return_value=fake_result),
        patch("app.repositories.screener.ScreenerRunRepository.save_run", return_value=fake_run),
        patch("app.services.ops.auto_screen.save_job_run_meta"),
        patch("app.services.ops.auto_screen.notify_delivery.deliver_text", side_effect=Exception("db down")),
    ):
        out = screen_post_close(db, user_id="u1")
    assert out.success is True
```

- [ ] **Step 2: 实现**：`_run_auto_screen` 成功分支末尾调用推送。推送文本格式：

```text
📊 盘中选股完成
配方 盘中多因子 命中 2 只（扫描 10，run=run-1）
1. 600519 贵州茅台 +2.31%
```

实现要点：
- `_format_screen_lines(label, result, run_id)`：取 `rows[:10]`，`symbol name change_pct`（`change_pct` 格式化 `{:+.2f}%`）
- 调用 `notify_delivery.deliver_text(db, user_id=user_id, event_type=f"ops.{job_id}", title=label, text=text)`，外包 `try/except Exception` 防主流程受扰

- [ ] **Step 3: 跑测试**：`pytest tests/test_ops_auto_screen.py -v` → 全部通过
- [ ] **Step 4: Commit**

---

### Task 6: 前端 API + 渠道页面 + 导航

**Files:**
- Create: `frontend/src/api/channels.ts`
- Create: `frontend/src/views/ChannelsView.vue`
- Modify: `frontend/src/components/AppShell.vue`（系统组新增「消息渠道」）
- Modify: `frontend/src/components/NavIcon.vue`（新增 `channels` 图标 + 类型）
- Modify: `frontend/src/router/index.ts`（`/channels` 路由）
- Modify: `frontend/src/views/NotifyView.vue`（无需改，保持）

**Interfaces:**
- Consumes: `api<T>(path, options)`、`AppShell`、`NavIcon`
- Produces: `channelApi.list() / create() / update() / remove() / test()`；`ChannelsView` 组件

- [ ] **Step 1: `frontend/src/api/channels.ts`**

```ts
import { api } from './client'

export type Channel = {
  id: string
  channel_type: string
  name: string
  webhook_url: string
  enabled: boolean
  created_at: string
  updated_at: string
}

export const channelApi = {
  list: () => api<{ items: Channel[] }>('/api/v1/channels'),
  create: (body: { name: string; webhook_url: string; enabled?: boolean }) =>
    api<Channel>('/api/v1/channels', { method: 'POST', body: JSON.stringify(body) }),
  update: (id: string, body: { name?: string; webhook_url?: string; enabled?: boolean }) =>
    api<Channel>(`/api/v1/channels/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),
  remove: (id: string) => api<{ ok: boolean }>(`/api/v1/channels/${id}`, { method: 'DELETE' }),
  test: (id: string) => api<{ ok: boolean; message: string }>(`/api/v1/channels/${id}/test`, { method: 'POST' }),
}
```

- [ ] **Step 2: `ChannelsView.vue`**：仿 `NotifyView.vue` 骨架（`AppShell title="消息渠道"`），含：
  - 加载/错误/空态、刷新
  - 渠道卡片网格：名称、类型徽章（飞书）、Webhook 脱敏（`https://open.feishu.cn/...xxxx`）、启用开关（PATCH enabled）、测试、删除（confirm）
  - 新增/编辑弹窗（Teleport + 遮罩）：name + webhook_url + enabled
  - 测试结果横幅（成功/失败原因）
- [ ] **Step 3: 导航接入**：`AppShell.vue` `active`/`NavKey` 类型加 `channels`，「系统」组加 `{ key: 'channels', label: '消息渠道', to: '/channels', enabled: true }`；`NavIcon.vue` 加 `channels` 图标与类型；router 加路由
- [ ] **Step 4: 验证**：`pnpm vue-tsc --noEmit` + `pnpm eslint` 通过
- [ ] **Step 5: Commit**

---

### Task 7: 全量验证

- [ ] **Step 1**: `pytest tests/test_notify_feishu.py tests/test_notify_delivery.py tests/test_channels_api.py tests/test_ops_auto_screen.py tests/test_notify_log.py -v`（backend）全部通过
- [ ] **Step 2**: 前端 `vue-tsc --noEmit` + `eslint` 通过
- [ ] **Step 3**: alembic 迁移冒烟：`alembic upgrade head` 无报错（或确认 down_revision 链正确）
- [ ] **Step 4**: 运行后端 + 前端 dev server，手动走一遍：新增渠道 → 测试发送 → 触发盘中选股查看推送
- [ ] **Step 5**: 最终 Commit（如需）

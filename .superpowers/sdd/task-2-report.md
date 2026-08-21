# Task 2 Report: 拆除 auth + channels 域兼容壳

## Status
✅ Done（Wave A Task 2 完成）

## Commits
- `ab0589d` refactor(domains): 拆除 auth/channels 域兼容壳

## 改动内容

### 删除 shim（10 个文件）
- `app/services/login_guard.py`
- `app/services/notify/__init__.py`、`delivery.py`、`feishu.py`（目录清空）
- `app/schemas/auth.py`、`app/schemas/channel.py`
- `app/repositories/user.py`、`app/repositories/channel.py`
- `app/api/v1/auth.py`、`app/api/v1/channels.py`

### 改消费者
- `app/api/deps.py`、`app/api/v1/ws.py`：`UserRepository` → `app.domains.auth.repository`
- `app/services/ops/auto_screen.py`：notify delivery → `app.domains.channels.notify`
- `app/api/v1/__init__.py`：auth/channels router 直连 `app.domains.*.router`，并从 `from app.api.v1 import (...)` 元组移除 auth、channels
- `tests/test_notify_feishu.py`、`tests/test_notify_delivery.py`：import 改 `app.domains.channels.notify.*`
- `tests/test_channels_api.py`：10 处 patch 目标 `app.repositories.channel.ChannelRepository` → `app.domains.channels.repository.ChannelRepository`（含 2 处函数内 import）

### 域导出前置验证
删除前已确认：`UserRepository`、`deliver_text`/`send_to_channel`、`FeishuSendError`/`send_feishu_webhook`、`ChannelRepository` 均在 domains 内导出。

## Tests
- 定向：`pytest tests/test_login_guard.py tests/test_auth_api.py tests/test_channels_api.py tests/test_notify_feishu.py tests/test_notify_delivery.py tests/test_security.py` → **39 passed**
- 全量：`pytest -q --tb=short` → **713 passed**
- 残留扫描：`rg "app.services.login_guard|app.services.notify|app.schemas.auth|app.schemas.channel|app.repositories.user|app.repositories.channel|app.api.v1.auth|app.api.v1.channels" app tests --glob '*.py'` → **零命中**

## Concerns
- 无。REST 路径/行为未改动，domains 实现未改动，未删其它域 shim。

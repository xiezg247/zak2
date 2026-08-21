### Task 2: auth + channels 拆壳

**Files 删除（8 个 shim）：**
- `app/services/login_guard.py`
- `app/services/notify/delivery.py`、`app/services/notify/feishu.py`（`app/services/notify/__init__.py` 一并删除，目录清空）
- `app/schemas/auth.py`、`app/schemas/channel.py`
- `app/repositories/user.py`、`app/repositories/channel.py`
- `app/api/v1/auth.py`、`app/api/v1/channels.py`

**改消费者（先改后删）：**
1. `app/api/deps.py`：`from app.repositories.user import UserRepository` → `from app.domains.auth.repository import UserRepository`
2. `app/api/v1/ws.py`：同上
3. `app/services/ops/auto_screen.py`：`from app.services.notify import delivery as notify_delivery` → `from app.domains.channels.notify import delivery as notify_delivery`
4. `app/api/v1/__init__.py`：auth/channels 改直连 domains：
   ```python
   from app.domains.auth.router import router as auth_router
   from app.domains.channels.router import router as channels_router
   # include_router(auth_router) / include_router(channels_router)
   ```
   （同时从 `from app.api.v1 import (...)` 元组移除 auth、channels 两项）
5. tests：
   - `tests/test_notify_feishu.py`：`from app.services.notify.feishu import ...` → `from app.domains.channels.notify.feishu import ...`
   - `tests/test_notify_delivery.py`：`from app.services.notify.delivery import ...`、`from app.services.notify.feishu import ...` → 对应 `app.domains.channels.notify.*`
   - `tests/test_channels_api.py`：10 处 `app.repositories.channel.ChannelRepository` → `app.domains.channels.repository.ChannelRepository`（含 2 处函数内 import `from app.repositories.channel import ChannelRepository` → `from app.domains.channels.repository import ChannelRepository`）

**先确认域内导出存在**（再改）：
- `app.domains.auth.repository` 导出 `UserRepository`
- `app.domains.channels.notify.delivery` 导出 `deliver_text`、`send_to_channel`
- `app.domains.channels.notify.feishu` 导出 `FeishuSendError`、`send_feishu_webhook`
- `app.domains.channels.repository` 导出 `ChannelRepository`

**测试：**
```bash
cd backend && uv run pytest tests/test_login_guard.py tests/test_auth_api.py \
  tests/test_channels_api.py tests/test_notify_feishu.py tests/test_notify_delivery.py \
  tests/test_security.py -v --tb=line
```
再加全量：`uv run pytest -q --tb=short`（全量绿才提交）。

**删壳后残留扫描必须零命中：**
```bash
rg "app.services.login_guard|app.services.notify|app.schemas.auth|app.schemas.channel|app.repositories.user|app.repositories.channel|app.api.v1.auth|app.api.v1.channels" app tests --glob '*.py'
```

**Commit**（简体中文 HEREDOC）：
`refactor(domains): 拆除 auth/channels 域兼容壳`

**Report** → `/Users/xiezhigang/Projects/me/zak2/.worktrees/backend-domains-phase6/.superpowers/sdd/task-2-report.md`

**禁止：** 改 REST 路径/行为；改 domains 实现；删其它域 shim。

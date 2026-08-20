# 后端 Phase 2（domains content）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 notes / feed / playbook（及 notify_log）迁入 `app.domains.content`，service 层改用 `AppError`，router 变薄且不再抛 `HTTPException`；旧路径保留 thin re-export。

**Architecture:** 复制 Phase 1 模板：`domains/content/{schemas,notes,feed,playbook,notify_log,router}.py`；`team_reports` 仍留在 `services/team`（跨域），由 content router/service 封装 404/400；新增 `UpstreamFailed`(502) 覆盖 Bilibili 上游错误。

**Tech Stack:** FastAPI、SQLAlchemy、现有 `AppError` handler、pytest。

**Spec:** [docs/superpowers/specs/2026-08-20-backend-architecture-refactor-design.md](../specs/2026-08-20-backend-architecture-refactor-design.md) Phase 2。

## Global Constraints

- 对外 REST 路径、JWT、Redis 键、ARQ job_id、响应 schema 字段不变
- commit subject/body 简体中文，格式 `<type>(<scope>): <简述>`
- domain router **禁止** import / 实例化 `*Repository`；**禁止** `HTTPException`
- domain service **禁止** FastAPI `HTTPException`（改用 `AppError` 子类）
- domain **禁止** import `app.api.v1`
- `get_current_user` 留在 `app.api.deps`；`models` 不搬包
- `services/plan/trading_risk.py`、`services/team/*`（除被 content 调用外）本 Phase 不迁
- 旧路径 `app.services.content.*`、`app.services.plan.playbook`、`app.schemas.content`、`app.api.v1.content` 保留 thin re-export

## File map（结束时）

| 路径 | 职责 |
|------|------|
| `backend/app/core/errors.py` | 新增 `UpstreamFailed` (502) |
| `backend/app/domains/content/__init__.py` | 域包 |
| `backend/app/domains/content/schemas.py` | 自 `schemas/content.py` |
| `backend/app/domains/content/notes.py` | 自 `services/content/notes.py`，AppError |
| `backend/app/domains/content/feed.py` | 自 `services/content/feed.py`，AppError |
| `backend/app/domains/content/notify_log.py` | 自 `services/content/notify_log.py` |
| `backend/app/domains/content/playbook.py` | 自 `services/plan/playbook.py`，AppError |
| `backend/app/domains/content/reports.py` | 薄封装 `team_reports` → AppError |
| `backend/app/domains/content/router.py` | 原 `api/v1/content.py` 路由，只调域内模块 |
| `backend/app/api/v1/content.py` | re-export router |
| `backend/app/services/content/*`、`services/plan/playbook.py`、`schemas/content.py` | re-export |

---

### Task 1: 新增 `UpstreamFailed` (502)

**Files:**
- Modify: `backend/app/core/errors.py`
- Modify: `backend/tests/test_app_errors.py`

**Interfaces:**
- Produces: `class UpstreamFailed(AppError): status_code = 502`

- [ ] **Step 1: 扩展测试（先失败）**

在 `test_app_errors.py` 的 `_client` 中增加：

```python
from app.core.errors import UpstreamFailed

@app.get("/up")
def up() -> None:
    raise UpstreamFailed("上游失败")

def test_upstream_failed_maps_502() -> None:
    resp = _client().get("/up")
    assert resp.status_code == 502
    assert resp.json()["message"] == "上游失败"
```

（把 `UpstreamFailed` 并入文件顶部既有 import。）

- [ ] **Step 2: 跑测确认失败**

```bash
cd backend && uv run pytest tests/test_app_errors.py::test_upstream_failed_maps_502 -v
```

Expected: FAIL（`UpstreamFailed` 不存在或 ImportError）

- [ ] **Step 3: 实现**

在 `backend/app/core/errors.py` 末尾追加：

```python
class UpstreamFailed(AppError):
    status_code = 502
```

- [ ] **Step 4: 跑测通过**

```bash
cd backend && uv run pytest tests/test_app_errors.py -v
```

Expected: 全部 PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/errors.py backend/tests/test_app_errors.py
git commit -m "$(cat <<'EOF'
feat(api): 新增 UpstreamFailed(502) 领域异常

供 content/feed 等上游 HTTP 失败映射，避免 service 抛 HTTPException。
EOF
)"
```

---

### Task 2: 迁入 content 域模块并替换 HTTPException

**Files:**
- Create: `backend/app/domains/content/__init__.py`（若尚无）
- Create: `backend/app/domains/content/schemas.py`（原样自 `schemas/content.py`）
- Create: `backend/app/domains/content/notes.py`、`feed.py`、`notify_log.py`、`playbook.py`
- Replace: `backend/app/schemas/content.py` → re-export
- Replace: `backend/app/services/content/{notes,feed,notify_log}.py` → re-export
- Replace: `backend/app/services/plan/playbook.py` → re-export
- Modify: `backend/tests/test_feed_search.py`、`test_feed_subscriptions.py`（`HTTPException` → 对应 `AppError` 子类）

**Interfaces:**
- 域内模块公开函数签名与迁移前相同
- 错误映射：
  - 原 404 → `NotFound`
  - 原 400 → `ValidationFailed`
  - 原 502 → `UpstreamFailed`
- 域内 import schemas：`from app.domains.content.schemas import ...`
- `playbook.py` / `notes.py` / `feed.py` **删除** `from fastapi import HTTPException`

- [ ] **Step 1: 创建域包与搬迁文件**

```python
# backend/app/domains/content/__init__.py
"""内容域：笔记 / Feed / 守则 playbook。"""
```

1. 复制 `schemas/content.py` → `domains/content/schemas.py`
2. 复制 `services/content/notes.py` → `domains/content/notes.py`，改 schemas import 为域内；将唯一 `HTTPException(400, ...)` 改为 `raise ValidationFailed("内容不能为空")`
3. 复制 `feed.py` → `domains/content/feed.py`，改 schemas import；按上表替换全部 HTTPException；schemas 用域内路径
4. 复制 `notify_log.py` → `domains/content/notify_log.py`（无 HTTPException 则仅改必要 import）
5. 复制 `services/plan/playbook.py` → `domains/content/playbook.py`，schemas 改域内；404→`NotFound`，400→`ValidationFailed`

`feed.py` 替换示例：

```python
from app.core.errors import NotFound, UpstreamFailed, ValidationFailed
# raise HTTPException(status_code=404, detail="订阅不存在")
raise NotFound("订阅不存在")
# raise HTTPException(status_code=502, detail=str(exc))
raise UpstreamFailed(str(exc)) from exc
# raise HTTPException(status_code=400, detail="mid 无效")
raise ValidationFailed("mid 无效")
```

- [ ] **Step 2: 旧路径 re-export**

```python
# backend/app/schemas/content.py
"""兼容壳：实现已迁至 app.domains.content.schemas。"""
from app.domains.content.schemas import *  # noqa: F403

# backend/app/services/content/notes.py
"""兼容壳。"""
from app.domains.content.notes import *  # noqa: F403

# backend/app/services/content/feed.py
"""兼容壳。"""
from app.domains.content.feed import *  # noqa: F403

# backend/app/services/content/notify_log.py
"""兼容壳。"""
from app.domains.content.notify_log import *  # noqa: F403

# backend/app/services/plan/playbook.py
"""兼容壳：实现已迁至 app.domains.content.playbook。"""
from app.domains.content.playbook import *  # noqa: F403
```

若 `schemas/content.py` 的 `*` re-export 导致 ruff 抱怨，改为显式导出原 `__all__` 中的全部符号（打开原文件列出）。

- [ ] **Step 3: 更新 feed 测试断言**

`test_feed_search.py` / `test_feed_subscriptions.py`：

- `from fastapi import HTTPException` → `from app.core.errors import NotFound, ValidationFailed, UpstreamFailed`（按实际用到的）
- `pytest.raises(HTTPException)` → `pytest.raises(ValidationFailed)` 或 `NotFound` / `UpstreamFailed`（对照原 status_code）
- 删除对 `ei.value.status_code` 的断言，或改为 `assert isinstance(ei.value, ValidationFailed)`；若原断言 `ei.value.detail`，改为 `ei.value.message`

也可改为 `from app.domains.content import feed as feed_svc`（推荐，patch 更稳）。

- [ ] **Step 4: 跑测**

```bash
cd backend && uv run pytest \
  tests/test_feed_search.py \
  tests/test_feed_subscriptions.py \
  tests/test_notify_log.py \
  tests/test_app_errors.py -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/domains/content backend/app/schemas/content.py \
  backend/app/services/content backend/app/services/plan/playbook.py \
  backend/tests/test_feed_search.py backend/tests/test_feed_subscriptions.py
git commit -m "$(cat <<'EOF'
refactor(content): notes/feed/playbook 迁入 domains 并改用 AppError

旧 services/schemas 路径保留兼容壳；feed 测试改为断言领域异常。
EOF
)"
```

---

### Task 3: content router 薄壳 + team reports 封装

**Files:**
- Create: `backend/app/domains/content/reports.py`
- Create: `backend/app/domains/content/router.py`
- Replace: `backend/app/api/v1/content.py` → re-export
- Test: `backend/tests/test_team_reports.py`、`test_list_pagination.py`（若有 API 级）

**Interfaces:**
- `reports.get_team_report(db, user_id, report_id) -> TeamReportOut`：缺失 → `NotFound("研报不存在")`
- `reports.list_team_reports(...)` / `list_team_reports_page(...)`：捕获 `ValueError` → `ValidationFailed(str(exc))`
- `router`：与现 `api/v1/content.py` 路径一致，调用 `notes`/`feed`/`playbook`/`reports`，**零** `HTTPException`

- [ ] **Step 1: 实现 reports 封装**

```python
# backend/app/domains/content/reports.py
from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.errors import NotFound, ValidationFailed
from app.domains.content.schemas import TeamReportListItem, TeamReportOut
from app.repositories.pagination import Page
from app.services.team import team_reports


def get_team_report(db: Session, user_id: str, report_id: int) -> TeamReportOut:
    row = team_reports.get_report(db, user_id, report_id)
    if not row:
        raise NotFound("研报不存在")
    return row


def list_team_reports(db: Session, user_id: str, vt_symbol: str) -> list[TeamReportListItem]:
    try:
        return team_reports.list_reports(db, user_id, vt_symbol)
    except ValueError as exc:
        raise ValidationFailed(str(exc)) from exc


def list_team_reports_page(
    db: Session, user_id: str, vt_symbol: str, *, page: int, page_size: int
) -> Page[TeamReportListItem]:
    try:
        return team_reports.list_reports_page(db, user_id, vt_symbol, page=page, page_size=page_size)
    except ValueError as exc:
        raise ValidationFailed(str(exc)) from exc
```

（若 `Page` 导入路径与仓库不符，以 `team_reports.list_reports_page` 返回类型为准。）

- [ ] **Step 2: 实现 router**

将现有 `api/v1/content.py` 复制为 `domains/content/router.py`，然后：

- import 改为 `app.domains.content.{notes,feed,playbook,reports,schemas}`
- 删除所有 `HTTPException`
- 研报三段改为调用 `reports.*`（不再手写 if/ValueError）
- `delete_note_entry`：若 `notes.delete_entry` 返回 False，改为在 router **或** notes 内抛 `NotFound`——**优先改 notes.delete_entry 在失败时 `raise NotFound("流水不存在")` 并返回 None 语义改为抛错**；若不想改 notes 签名，在 router：

```python
if not notes_svc.delete_entry(...):
    raise NotFound("流水不存在")  # 禁止：router 不应抛业务异常若约定 service 抛
```

**约定：** 修改 `domains/content/notes.py` 的 `delete_entry`：找不到时 `raise NotFound("流水不存在")`，成功返回 `None`；router 只调用不判断。同步更新兼容壳消费方（若有依赖 bool 返回值的测试）。

检查 `delete_entry` 当前签名与调用点：

```bash
rg "delete_entry" backend -g '*.py'
```

若仅 content router 使用，直接改抛 `NotFound`。

- [ ] **Step 3: api 兼容壳**

```python
# backend/app/api/v1/content.py
"""兼容壳：路由实现已迁至 app.domains.content.router。"""
from app.domains.content.router import router

__all__ = ["router"]
```

确认 `api/v1/__init__.py` 仍 `include_router(content.router)`。

- [ ] **Step 4: 分层检查 + 测试**

```bash
cd backend && (rg "HTTPException|Repository" app/domains/content/router.py && exit 1 || echo ok)
uv run pytest \
  tests/test_feed_search.py \
  tests/test_feed_subscriptions.py \
  tests/test_team_reports.py \
  tests/test_list_pagination.py \
  tests/test_notify_log.py \
  tests/test_app_errors.py -v
```

Expected: `ok` 且 PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/domains/content backend/app/api/v1/content.py
git commit -m "$(cat <<'EOF'
refactor(content): API 路由迁入 domains 并由域内模块承接

研报经 reports 封装映射 AppError；api/v1/content 仅保留兼容壳。
EOF
)"
```

---

### Task 4: 回归与 domains README 备注

**Files:**
- Modify: `backend/app/domains/README.md`（补充 content 已迁入一行即可）
- Verify tests

- [ ] **Step 1: README 追加**

在 `backend/app/domains/README.md` 末尾加：

```markdown
## 已迁入

- `auth` / `channels`（Phase 1）
- `content`（notes / feed / playbook / notify_log，Phase 2）
```

- [ ] **Step 2: 全量相关回归**

```bash
cd backend && uv run pytest \
  tests/test_app_errors.py \
  tests/test_feed_search.py \
  tests/test_feed_subscriptions.py \
  tests/test_ops_sync_bilibili_feed.py \
  tests/test_team_reports.py \
  tests/test_list_pagination.py \
  tests/test_notify_log.py \
  tests/test_auth_api.py \
  tests/test_channels_api.py -v
```

Expected: 全部 PASS

- [ ] **Step 3: Commit**

```bash
git add backend/app/domains/README.md
git commit -m "$(cat <<'EOF'
docs(domains): 标注 content 域已迁入

与 Phase 2 落地同步，便于后续域迁移对照。
EOF
)"
```

---

## Spec coverage

| Spec Phase 2 项 | Task |
|-----------------|------|
| content 垂直切片 | Task 2–3 |
| API 变薄 / 无 HTTPException in domain service+router | Task 2–3 |
| 兼容壳 | Task 2–3 |
| 与前端 features 对齐（目录语义） | domains/content |

## Out of scope

- 迁 `team_reports` / `trading_risk` / watchlist
- 拆除兼容壳
- 改前端

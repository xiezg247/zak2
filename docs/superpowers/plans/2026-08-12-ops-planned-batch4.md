# Ops planned 第四批（概念 / 1m skipped 壳）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 `prefetch_concept_board`、`fill_focus_pool_minute` 升级为可跑诚实 skipped 壳（默认定时关）；catalog 清空 planned。

**Architecture:** 每 job 一薄模块（恒 skipped + meta）+ 单测；统一注册 RUNNABLE/RUNNERS/DEFAULT_CRON；planned 守卫测试改为 mock `job_kind_for`。

**Tech Stack:** SQLAlchemy Session、pytest mock

**Spec:** `docs/superpowers/specs/2026-08-12-ops-planned-batch4-design.md`

## Global Constraints

- 只改 zak2；不改 zak / vnpy-*
- 不写概念缓存、不写 1m K
- 恒 `skipped=True` + `success=False` + `save_job_run_meta(..., last_success=False)`
- enabled 默认 false；仅加 DEFAULT_CRON
- commit message 简体中文：`<type>(<scope>): <简述>`

## File map

| 路径 | 职责 |
|------|------|
| `ops_prefetch_concept_board.py` | concept skipped 壳 |
| `ops_fill_focus_pool_minute.py` | 1m skipped 壳 |
| `ops_catalog` / `ops_runners` / `scheduler_defaults` | 注册 |
| `tests/test_ops_prefetch_concept_board.py` 等 | 单测 |
| `test_ops_job_kind.py` / `test_ops_job_guards.py` | 无 planned + mock 守卫 |
| `docs/product-roadmap.md` / `smoke-checklist.md` | 文档 |

---

### Task 1: `prefetch_concept_board` skipped 壳

**Files:**
- Create: `backend/app/services/ops_prefetch_concept_board.py`
- Create: `backend/tests/test_ops_prefetch_concept_board.py`

**Interfaces:**
- Produces: `prefetch_concept_board(db: Session) -> dict[str, Any]`
- Consumes: `save_job_run_meta`

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_ops_prefetch_concept_board.py
from unittest.mock import MagicMock, patch

from app.services import ops_prefetch_concept_board as m


def test_concept_skips() -> None:
    db = MagicMock()
    with patch("app.services.ops_prefetch_concept_board.save_job_run_meta") as save:
        out = m.prefetch_concept_board(db)
    assert out["skipped"] is True
    assert out["success"] is False
    assert "概念" in out["message"]
    save.assert_called_once()
    assert save.call_args.kwargs["last_success"] is False
```

- [ ] **Step 2: 跑测确认失败**

```bash
cd backend && uv run pytest tests/test_ops_prefetch_concept_board.py -v
```

Expected: FAIL（模块不存在）

- [ ] **Step 3: 实现**

```python
"""同花顺概念预拉占位：zak2 尚未接入概念预热落点。"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.services.ops_scheduler import save_job_run_meta

JOB_ID = "prefetch_concept_board"
_MESSAGE = "zak2 尚未接入同花顺概念预热落点，无法预拉 concept board"


def prefetch_concept_board(db: Session) -> dict[str, Any]:
    save_job_run_meta(db, JOB_ID, last_message=_MESSAGE, last_success=False)
    return {"success": False, "skipped": True, "message": _MESSAGE}
```

- [ ] **Step 4: 跑测确认通过**

```bash
cd backend && uv run pytest tests/test_ops_prefetch_concept_board.py -q
```

Expected: 1 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/ops_prefetch_concept_board.py backend/tests/test_ops_prefetch_concept_board.py
git commit -m "$(cat <<'EOF'
feat(ops): 实现 prefetch_concept_board 诚实 skipped 壳

尚未接入同花顺概念预热落点，仅写 meta。
EOF
)"
```

---

### Task 2: `fill_focus_pool_minute` skipped 壳

**Files:**
- Create: `backend/app/services/ops_fill_focus_pool_minute.py`
- Create: `backend/tests/test_ops_fill_focus_pool_minute.py`

**Interfaces:**
- Produces: `fill_focus_pool_minute(db: Session) -> dict[str, Any]`
- Consumes: `save_job_run_meta`

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_ops_fill_focus_pool_minute.py
from unittest.mock import MagicMock, patch

from app.services import ops_fill_focus_pool_minute as m


def test_minute_skips() -> None:
    db = MagicMock()
    with patch("app.services.ops_fill_focus_pool_minute.save_job_run_meta") as save:
        out = m.fill_focus_pool_minute(db)
    assert out["skipped"] is True
    assert out["success"] is False
    assert "1m" in out["message"] or "分钟" in out["message"]
    save.assert_called_once()
    assert save.call_args.kwargs["last_success"] is False
```

- [ ] **Step 2: 跑测确认失败**

```bash
cd backend && uv run pytest tests/test_ops_fill_focus_pool_minute.py -v
```

Expected: FAIL

- [ ] **Step 3: 实现**

```python
"""关注池 1m K 补全占位：zak2 尚未接入分钟线补全管线。"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.services.ops_scheduler import save_job_run_meta

JOB_ID = "fill_focus_pool_minute"
_MESSAGE = "zak2 尚未接入关注池 1m K 补全管线"


def fill_focus_pool_minute(db: Session) -> dict[str, Any]:
    save_job_run_meta(db, JOB_ID, last_message=_MESSAGE, last_success=False)
    return {"success": False, "skipped": True, "message": _MESSAGE}
```

- [ ] **Step 4: 跑测确认通过**

```bash
cd backend && uv run pytest tests/test_ops_fill_focus_pool_minute.py -q
```

Expected: 1 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/ops_fill_focus_pool_minute.py backend/tests/test_ops_fill_focus_pool_minute.py
git commit -m "$(cat <<'EOF'
feat(ops): 实现 fill_focus_pool_minute 诚实 skipped 壳

尚未接入 1m 补全管线，仅写 meta。
EOF
)"
```

---

### Task 3: 注册 + planned 测试迁移 + 文档 + check

**Files:**
- Modify: `ops_catalog.py` — RUNNABLE 加两 id；JobSpec 占位文案
- Modify: `ops_runners.py` — import + RUNNERS
- Modify: `scheduler_defaults.py` — DEFAULT_CRON
- Modify: `tests/test_ops_catalog.py`、`test_ops_job_kind.py`、`test_ops_job_guards.py`、`test_scheduler_defaults.py`（按需）
- Modify: `docs/product-roadmap.md`、`docs/smoke-checklist.md`

**Interfaces:**
- Consumes: Task 1/2 导出函数
- Produces: 两 id ∈ RUNNABLE；catalog 无 planned；guards 仍测 planned 守卫（via mock）

- [ ] **Step 1: 注册**

`RUNNABLE_JOB_IDS` 增加 `"prefetch_concept_board"`、`"fill_focus_pool_minute"`。

JobSpec 描述示例：
- concept：`占位：尚未接入同花顺概念预热落点（Web 可跑 → skipped）`
- minute：`占位：尚未接入关注池 1m 补全管线（Web 可跑 → skipped）`

`RUNNERS`：
```python
"prefetch_concept_board": ops_prefetch_concept_board.prefetch_concept_board,
"fill_focus_pool_minute": ops_fill_focus_pool_minute.fill_focus_pool_minute,
```

`DEFAULT_CRON`：
```python
"prefetch_concept_board": {"hour": 17, "minute": 30, "day_of_week": "mon-fri"},
"fill_focus_pool_minute": {"hour": 19, "minute": 0, "day_of_week": "mon-fri"},
```

- [ ] **Step 2: 改 job_kind / guards 测试**

`test_ops_job_kind.py`：
- 断言 `job_kind_for("prefetch_concept_board") == "runnable"`
- 断言 `job_kind_for("fill_focus_pool_minute") == "runnable"`
- 新增（或替换 planned 断言）：

```python
from app.services.ops_catalog import JOB_SPECS

def test_no_planned_jobs_in_catalog() -> None:
    planned = [s.job_id for s in JOB_SPECS if job_kind_for(s.job_id) == "planned"]
    assert planned == []
```

`test_ops_job_guards.py`：
- `test_patch_planned_job_enabled_true_returns_400`：patch `app.api.v1.ops` 或 scheduler 所用的 `job_kind_for`，对任意已存在 job_id（如 `purge_stale_cache`）返回 `"planned"`，再 PATCH enabled=True → 400，且 `patch_job_enabled` 未调用。
- `test_patch_planned_job_enabled_false_returns_200`：同样 mock kind=planned，enabled=False → 200。
- 合成 `_planned_job_row` 的 `job_id` 可改为任意 id；关键是 `job_kind_for` mock。

示例（enabled=True）：

```python
def test_patch_planned_job_enabled_true_returns_400() -> None:
    client = _api_client()
    with (
        patch("app.api.v1.ops.ops_scheduler.job_kind_for", return_value="planned"),
        patch("app.services.ops_scheduler.patch_job_enabled") as p,
    ):
        r = client.patch("/api/v1/ops/scheduler/jobs/purge_stale_cache", json={"enabled": True})
    assert r.status_code == 400
    p.assert_not_called()
```

（若 API 从别处 import `job_kind_for`，按实际 patch 路径调整；实现时先读 `ops.py` 确认。）

- [ ] **Step 3: 文档**

`product-roadmap.md` 增加：  
`8. ~~Ops planned 第四批~~（已完成 → [spec](...batch4-design.md)）：prefetch_concept_board / fill_focus_pool_minute 可跑占位（恒 skipped）；catalog 已无 planned`

`smoke-checklist.md`：可跑列表加入两 job；手动跑期望 skipped；cron 17:30 / 19:00；筛选「未实现」可为空。

- [ ] **Step 4: check.sh**

```bash
./scripts/check.sh
```

Expected: pytest 全绿 + frontend build OK

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/ops_catalog.py backend/app/services/ops_runners.py \
  backend/app/services/scheduler_defaults.py backend/tests/test_ops_catalog.py \
  backend/tests/test_ops_job_kind.py backend/tests/test_ops_job_guards.py \
  backend/tests/test_scheduler_defaults.py docs/product-roadmap.md docs/smoke-checklist.md
git commit -m "$(cat <<'EOF'
feat(ops): 注册概念预拉与关注池1m为可跑占位

catalog 清空 planned；守卫测试改 mock；更新路线图与 smoke。
EOF
)"
```

---

## Spec coverage（自审）

| Spec 要求 | Task |
|-----------|------|
| concept skipped 壳 | 1 |
| minute skipped 壳 | 2 |
| RUNNABLE/cron/文档；无 planned；guards mock | 3 |

无 TBD。

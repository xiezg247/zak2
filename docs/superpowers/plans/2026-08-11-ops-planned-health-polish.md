# Ops planned 透明化与健康面板打磨 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ops 健康区展示调度锁；任务表用 `job_kind` 分组+筛选，非可跑禁用开关/执行并由 API 400 兜底。

**Architecture:** 后端在 `list_scheduler_jobs` 增加稳定枚举 `job_kind`；PATCH enable / POST run 拒绝 `process`/`planned`。前端补 `scheduler_lock` 卡与 Health 类型；OpsView 按 `job_kind` 筛选分组并禁用控件。

**Tech Stack:** FastAPI、Pydantic、Vue3、pytest

**Spec:** `docs/superpowers/specs/2026-08-11-ops-planned-health-polish-design.md`

**Worktree:** `/Users/xiezhigang/Projects/me/zak2/.worktrees/zak2-independent-evolution`（分支 `feature/zak2-independent-evolution`）

## Global Constraints

- 只改 zak2；不改 zak / vnpy-*
- `job_kind` 取值仅为 `runnable` | `process` | `planned`
- `collect_quotes` → `process`；∈ `RUNNABLE_JOB_IDS` → `runnable`；其余 → `planned`
- 分组/筛选以 `job_kind` 为准，不解析中文 `status_label`
- 不做 toolbar 大一统、不实现新 planned job、不展示持锁列表
- commit message 简体中文：`<type>(<scope>): <简述>`

## File map

| 路径 | 职责 |
|------|------|
| `backend/app/services/ops_catalog.py` 或 `ops_scheduler.py` | `job_kind_for(job_id)` |
| `backend/app/schemas/ops.py` | `SchedulerJobOut.job_kind`；`HealthOut.scheduler_lock` 可加 `ok` |
| `backend/app/api/v1/ops.py` | PATCH/POST 守卫 |
| `backend/app/services/ops_health.py` | 可选 `scheduler_lock.ok` |
| `frontend/src/api/ops.ts` | Health / SchedulerJob 类型 |
| `frontend/src/views/OpsView.vue` | 锁卡 + 筛选分组 + 禁用 |
| `docs/smoke-checklist.md` / `docs/product-roadmap.md` | 验收与路线图 |

---

### Task 1: 后端 `job_kind` + API 守卫

**Files:**
- Modify: `backend/app/services/ops_scheduler.py`
- Modify: `backend/app/schemas/ops.py`
- Modify: `backend/app/api/v1/ops.py`
- Modify: `backend/tests/test_ops_run_hints.py`（或新建 `test_ops_job_kind.py`）
- Test: `backend/tests/test_ops_job_kind.py`

**Interfaces:**
- Produces: `job_kind_for(job_id: str) -> Literal["runnable","process","planned"]`
- Produces: `list_scheduler_jobs` 每行含 `job_kind`
- Produces: PATCH enable / POST run 对非 runnable → 400

- [ ] **Step 1: 写失败测试**

`backend/tests/test_ops_job_kind.py`:

```python
from unittest.mock import MagicMock, patch

from app.services.ops_scheduler import job_kind_for, list_scheduler_jobs


def test_job_kind_mapping() -> None:
    assert job_kind_for("purge_stale_cache") == "runnable"
    assert job_kind_for("collect_quotes") == "process"
    assert job_kind_for("enrich_market_quotes") == "planned"


def test_list_jobs_includes_job_kind() -> None:
    db = MagicMock()
    with patch("app.services.ops_scheduler.load_scheduler_config", return_value={"config": {}}), patch(
        "app.services.ops_scheduler.load_job_run_meta", return_value=None
    ):
        rows = {r["job_id"]: r for r in list_scheduler_jobs(db)}
    assert rows["collect_quotes"]["job_kind"] == "process"
    assert rows["purge_stale_cache"]["job_kind"] == "runnable"
    assert rows["enrich_market_quotes"]["job_kind"] == "planned"
```

另在 `backend/tests/test_ops_job_guards.py`（或同文件用 TestClient）：

```python
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.core.db import get_db
from app.main import create_app
from app.models.user import User


def _client() -> TestClient:
    app = create_app()
    user = User(
        id="u1",
        username="t",
        display_name="t",
        password_hash="x",
        is_active=True,
        created_at=__import__("datetime").datetime.now(__import__("datetime").UTC),
        updated_at=__import__("datetime").datetime.now(__import__("datetime").UTC),
    )

    def _user():
        return user

    def _db():
        yield MagicMock()

    app.dependency_overrides[get_current_user] = _user
    app.dependency_overrides[get_db] = _db
    return TestClient(app)


def test_patch_planned_job_returns_400() -> None:
    client = _client()
    with patch("app.services.ops_scheduler.patch_job_enabled") as p:
        r = client.patch("/api/v1/ops/scheduler/jobs/enrich_market_quotes", json={"enabled": True})
    assert r.status_code == 400
    p.assert_not_called()


def test_run_process_job_returns_400() -> None:
    client = _client()
    r = client.post("/api/v1/ops/scheduler/jobs/collect_quotes/run")
    assert r.status_code == 400
```

（若项目 `User` 构造或依赖注入模式不同，对齐现有 `test_plan_draft.py` / ops 测试写法，保持断言：planned/process → 400，且不调用 `patch_job_enabled`。）

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && uv run pytest tests/test_ops_job_kind.py tests/test_ops_job_guards.py -v`  
Expected: FAIL（`job_kind_for` 未定义或 PATCH 仍 200）

- [ ] **Step 3: 实现**

在 `ops_scheduler.py`:

```python
from typing import Literal

JobKind = Literal["runnable", "process", "planned"]


def job_kind_for(job_id: str) -> JobKind:
    if job_id in RUNNABLE_JOB_IDS:
        return "runnable"
    if job_id == "collect_quotes":
        return "process"
    return "planned"
```

在 `list_scheduler_jobs` 的 `row` 中增加 `"job_kind": job_kind_for(spec.job_id)`；可用 `job_kind` 推导现有 `runnable`/`status_label`/`run_hint`（避免三处 if 漂移）。

`schemas/ops.py` `SchedulerJobOut`:

```python
job_kind: Literal["runnable", "process", "planned"] = "runnable"
```

`ops.py` `patch_scheduler_job`：在 try 前：

```python
from app.services.ops_scheduler import job_kind_for

kind = job_kind_for(job_id)
if kind != "runnable":
    detail = (
        "独立进程请启动 quote-collector"
        if kind == "process"
        else "未实现任务不可启用"
    )
    raise HTTPException(status_code=400, detail=detail)
```

`run_scheduler_job`：现有 `if job_id not in RUNNABLE_JOB_IDS` 已 400；确认对 `collect_quotes` 返回 400，detail 可改为更清晰文案（可选）。

- [ ] **Step 4: 跑测试确认通过**

```bash
cd backend && uv run pytest tests/test_ops_job_kind.py tests/test_ops_job_guards.py tests/test_ops_run_hints.py tests/test_ops_scheduler_defaults.py -q
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/ops_scheduler.py backend/app/schemas/ops.py \
  backend/app/api/v1/ops.py backend/tests/test_ops_job_kind.py backend/tests/test_ops_job_guards.py
git commit -m "$(cat <<'EOF'
feat(ops): 增加 job_kind 并拒绝非可跑启用/执行

稳定枚举供前端分组；process/planned 写路径返回 400。
EOF
)"
```

---

### Task 2: 健康面板调度锁卡

**Files:**
- Modify: `backend/app/services/ops_health.py`（可选 `ok`）
- Modify: `backend/app/schemas/ops.py`（若 HealthOut 用 Typed dict / model 约束 lock）
- Modify: `frontend/src/api/ops.ts`
- Modify: `frontend/src/views/OpsView.vue`（仅健康 cards 段）
- Test: `backend/tests/test_ops_health_lock.py`（轻量）

**Interfaces:**
- Produces: `health.scheduler_lock` 含 `ok`（=`redis_ok`）、`backend`、`ttl_seconds`、`key_prefix`
- Produces: OpsView 第 7 张「调度锁」卡

- [ ] **Step 1: 写失败测试**

```python
from unittest.mock import MagicMock, patch

from app.services import ops_health


def test_health_scheduler_lock_has_ok() -> None:
    db = MagicMock()
    with patch.object(ops_health, "get_quote_store") as gs, patch.object(
        ops_health, "collector_health", return_value={}
    ), patch.object(ops_health.mcp_client, "probe_connection", return_value={}):
        store = MagicMock()
        store.meta.return_value = {"available": True, "updated_at": None, "quote_count": 0}
        gs.return_value = store
        snap = ops_health.health_snapshot(db)
    assert snap["scheduler_lock"]["ok"] is True
    assert "key_prefix" in snap["scheduler_lock"]
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && uv run pytest tests/test_ops_health_lock.py -v`  
Expected: FAIL（无 `ok`）

- [ ] **Step 3: 实现后端 + 前端卡**

`ops_health.py` 中 `scheduler_lock`：

```python
"scheduler_lock": {
    "ok": redis_ok,
    "backend": "redis",
    "ttl_seconds": scheduler_lock.clamp_ttl(settings.scheduler_lock_ttl_seconds),
    "key_prefix": scheduler_lock.LOCK_KEY_PREFIX,
},
```

`ops.ts` `Health` 增加：

```typescript
scheduler_lock?: {
  ok?: boolean
  backend?: string
  ttl_seconds?: number
  key_prefix?: string
}
```

（`quote_collector` 若已有则保留。）

`OpsView.vue` 健康 cards 内，在 MCP 卡后（或 Redis 后）增加：

```vue
<div class="card" :class="{ bad: health.scheduler_lock?.ok === false || !health.redis.ok }">
  <h3>调度锁</h3>
  <p>
    {{
      health.scheduler_lock?.ok === false || !health.redis.ok
        ? '不可用'
        : `Redis 锁 · TTL ${health.scheduler_lock?.ttl_seconds ?? '—'}s`
    }}
  </p>
  <p class="muted">{{ health.scheduler_lock?.key_prefix || 'zak2:scheduler:lock:' }}</p>
</div>
```

- [ ] **Step 4: 跑测试**

```bash
cd backend && uv run pytest tests/test_ops_health_lock.py -q
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/ops_health.py backend/app/schemas/ops.py \
  backend/tests/test_ops_health_lock.py frontend/src/api/ops.ts frontend/src/views/OpsView.vue
git commit -m "$(cat <<'EOF'
feat(ops): 健康面板展示调度锁卡片

补齐 Redis 锁 TTL/前缀与可达状态，对齐 smoke 验收。
EOF
)"
```

---

### Task 3: OpsView 筛选、分组与禁用

**Files:**
- Modify: `frontend/src/api/ops.ts`（`job_kind`）
- Modify: `frontend/src/views/OpsView.vue`
- Optional: `frontend/src/views/opsJobGroups.ts` + 轻量测试（若前端无 vitest，则纯函数放 `opsJobGroups.ts` 并在注释中说明；或仅 Vue computed，靠手工 smoke）

**Interfaces:**
- Consumes: `SchedulerJob.job_kind`
- Produces: 筛选 `全部|可跑|独立进程|未实现`；分组节；非 runnable 开关 disabled

- [ ] **Step 1: 类型 + 分组纯函数（可测）**

`frontend/src/views/opsJobGroups.ts`:

```typescript
import type { SchedulerJob } from '../api/ops'

export type JobKind = 'runnable' | 'process' | 'planned'
export type JobFilter = 'all' | JobKind

export const KIND_ORDER: JobKind[] = ['runnable', 'process', 'planned']
export const KIND_TITLE: Record<JobKind, string> = {
  runnable: '可跑',
  process: '独立进程',
  planned: '未实现',
}

export function filterJobs(jobs: SchedulerJob[], filter: JobFilter): SchedulerJob[] {
  if (filter === 'all') return jobs
  return jobs.filter((j) => j.job_kind === filter)
}

export function groupJobs(jobs: SchedulerJob[]): { kind: JobKind; title: string; items: SchedulerJob[] }[] {
  return KIND_ORDER.map((kind) => ({
    kind,
    title: KIND_TITLE[kind],
    items: jobs.filter((j) => j.job_kind === kind),
  })).filter((g) => g.items.length > 0)
}
```

`ops.ts`：`job_kind: 'runnable' | 'process' | 'planned'`

若仓库无前端单测框架，跳过自动测，在 Step 4 用手工验证；有 vitest 则加：

```typescript
import { describe, expect, it } from 'vitest'
import { filterJobs, groupJobs } from './opsJobGroups'

const sample = [
  { job_id: 'a', job_kind: 'runnable' },
  { job_id: 'collect_quotes', job_kind: 'process' },
  { job_id: 'x', job_kind: 'planned' },
] as any

describe('opsJobGroups', () => {
  it('filters', () => {
    expect(filterJobs(sample, 'planned')).toHaveLength(1)
  })
  it('groups in order', () => {
    expect(groupJobs(sample).map((g) => g.kind)).toEqual(['runnable', 'process', 'planned'])
  })
})
```

- [ ] **Step 2: 若有 vitest 则先跑红；无则进入实现**

- [ ] **Step 3: 改 OpsView**

```typescript
import { computed, onMounted, ref } from 'vue'
import { filterJobs, groupJobs, type JobFilter } from './opsJobGroups'

const jobFilter = ref<JobFilter>('all')
const jobGroups = computed(() => groupJobs(filterJobs(jobs.value, jobFilter.value)))
```

`toggle` 开头：

```typescript
if (job.job_kind !== 'runnable') return
```

模板：定时任务 toolbar 旁加筛选：

```vue
<select v-model="jobFilter">
  <option value="all">全部</option>
  <option value="runnable">可跑</option>
  <option value="process">独立进程</option>
  <option value="planned">未实现</option>
</select>
```

表体改为：

```vue
<template v-for="g in jobGroups" :key="g.kind">
  <tr class="section">
    <td colspan="5"><strong>{{ g.title }}</strong>· {{ g.items.length }}</td>
  </tr>
  <tr v-for="j in g.items" :key="j.job_id">
    <!-- 任务/调度/上次运行同前 -->
    <td>
      <label class="switch">
        <input
          type="checkbox"
          :checked="j.enabled"
          :disabled="!!busy || j.job_kind !== 'runnable'"
          @change="toggle(j)"
        />
      </label>
    </td>
    <!-- ... -->
    <td>
      <button
        v-if="j.job_kind === 'runnable'"
        type="button"
        class="ghost"
        :disabled="!!busy"
        @click="runJob(j.job_id, false)"
      >
        异步执行
      </button>
      <span v-else class="muted tip" :title="j.run_hint || ''">{{ j.status_label || KIND_TITLE[j.job_kind] }}</span>
    </td>
  </tr>
</template>
```

（对齐现有 switch/markup；以当前 OpsView 结构为准微调，保持 `job_kind !== 'runnable'` 禁用与操作列逻辑。）

- [ ] **Step 4: 验证**

```bash
cd frontend && npm run build
cd ../backend && uv run pytest tests/test_ops_job_kind.py tests/test_ops_job_guards.py -q
```

Expected: build OK；后端测 PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/api/ops.ts frontend/src/views/OpsView.vue frontend/src/views/opsJobGroups.ts
git commit -m "$(cat <<'EOF'
feat(ops): 任务表按 job_kind 筛选分组并禁用非可跑

默认可跑/独立进程/未实现分节，防止误开 planned 调度。
EOF
)"
```

---

### Task 4: 文档与总验收

**Files:**
- Modify: `docs/smoke-checklist.md`
- Modify: `docs/product-roadmap.md`

- [ ] **Step 1: 更新 smoke**

在 `/ops` 相关条目增加：

- 健康区有「调度锁」卡（TTL / 前缀）  
- 任务表可筛选；默认分组  
- planned/独立进程开关不可点；可跑可执行  

- [ ] **Step 2: 更新 roadmap**

近期待办 #2 改为已完成或划掉，并指向本 spec。

- [ ] **Step 3: 跑 check**

```bash
./scripts/check.sh
```

Expected: pytest + frontend build 绿

- [ ] **Step 4: Commit**

```bash
git add docs/smoke-checklist.md docs/product-roadmap.md
git commit -m "$(cat <<'EOF'
docs: Ops 透明化验收与路线图收口

smoke 补调度锁与任务分组；roadmap 勾掉对应待办。
EOF
)"
```

- [ ] **Step 5: 完成**

无空 commit。

---

## Spec coverage

| Spec | Task |
|------|------|
| 调度锁卡 + Health 类型 | 2 |
| `job_kind` | 1 |
| 分组 + 筛选 | 3 |
| 前端禁用 + API 400 | 1 + 3 |
| smoke / roadmap | 4 |
| 不做 toolbar 统一 | 遵守 |

## 执行交接

Plan 已保存到 `docs/superpowers/plans/2026-08-11-ops-planned-health-polish.md`。

# 后端 Phase 5（ops 边界 + auto_schedules + 异常统一）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 `auto_schedules`（自动选股计划）迁入 `app.domains.auto_schedules` 垂直切片；`ops` / `jobs` 路由薄化且 HTTPException 改 AppError；清理 `services/ops` 死代码异常分支；job 注册维持清晰。

**Architecture:** 两波可独立验收（Wave A auto_schedules 域 → Wave B ops/jobs 路由与横切异常统一）。worker / embedded_scheduler 仅改 import 或走兼容壳，不重写拓扑。

**Tech Stack:** FastAPI、SQLAlchemy、`AppError`、pytest、既有 ARQ enqueue。

**Spec:** [docs/superpowers/specs/2026-08-20-backend-architecture-refactor-design.md](../specs/2026-08-20-backend-architecture-refactor-design.md) Phase 5。

## Global Constraints

- 对外 REST 路径、JWT、Redis 键、ARQ job_id / `SCREENER_FUNCS` / `BACKTEST_FUNCS` / auto_schedule ARQ 函数名不变
- commit 简体中文 `<type>(<scope>): <简述>`
- domain router **禁止** `HTTPException` 与直连 `*Repository`
- domain service **禁止** FastAPI `HTTPException`（→ `AppError`）；`validate_task_input` 的 `ValueError` 由 service 映射为 `ValidationFailed`，不泄出
- domain **禁止** import `app.api.v1`；`models` 不搬
- 旧 `app.repositories.auto_schedule`、`app.schemas.auto_schedule`、`app.services.ops.auto_schedule{,_time}`、`app.api.v1.{auto_schedules,ops,jobs}` 保留 re-export
- 不重写 ops/worker 拓扑；`worker/tasks_auto_schedule.py` 可改 import 指向域内实现（非拓扑重写）；`embedded_scheduler` 保持走兼容壳或改域内 import 均可
- 域内跨域引用一律走 `app.domains.*`（screener engine/presets、channels notify delivery）

---

## Wave A — auto_schedules 域

### Task 1: 迁 schemas + repository + services/ops/auto_schedule{,_time}（AppError）

**Files:**
- Create: `domains/auto_schedules/__init__.py`、`schemas.py`、`repository.py`、`service.py`、`auto_schedule_time.py`、`router.py`
- Replace: `schemas/auto_schedule.py`、`repositories/auto_schedule.py`、`services/ops/auto_schedule.py`、`services/ops/auto_schedule_time.py` → re-export；`api/v1/auto_schedules.py` → re-export
- Modify: 测试断言 HTTPException → AppError（`rg HTTPException tests/test_auto_schedule*`）

**映射：** `except HTTPException` → `except AppError`；`exc.detail` → `exc.message`（AppError 无 detail 属性，message 即用户消息）。

**细节：**
- `service.py` 承接现 `services/ops/auto_schedule.py` 全部函数（validate_task_input/run_task/poll_due_tasks/_notify_result/_record_run）+ 现 router 的 CRUD 逻辑（list/create/update/enable/delete）
- 跨域 import 改域内：
  - `app.repositories.screener` → `app.domains.screener.repository`（ScreenerRunRepository）
  - `app.services.screener.engine` → `app.domains.screener.engine`（run_recipe_screen）
  - `app.services.screener.presets` → `app.domains.screener.presets`（get_builtin_recipe）
  - `app.services.notify.delivery` → `app.domains.channels.notify.delivery`
  - `app.services.ops.auto_schedule_time` → `app.domains.auto_schedules.auto_schedule_time`
- `auto_schedule_time.py` 为纯工具（parse_times/parse_days_of_week/matches_now），随域迁入，`app/services/ops/auto_schedule_time.py` 保留 re-export
- 旧 `services/ops/auto_schedule.py`：`sys.modules[__name__] = 域模块` 别名（与 screener/market 一致）
- `repositories/auto_schedule.py`：显式 `__all__` re-export `AutoScheduleRepository`

- [ ] **Step 1:** 复制 schemas/repository/auto_schedule/auto_schedule_time → 域内，改内部 import
- [ ] **Step 2:** 删除 `from fastapi import HTTPException`；`except HTTPException` → `except AppError`，`exc.detail` → `exc.message`
- [ ] **Step 3:** 旧路径 re-export（schemas 显式 `__all__`；services/ops/auto_schedule 与 auto_schedule_time `sys.modules` 别名；repositories 显式）
- [ ] **Step 4:** 更新测试断言（`rg HTTPException tests/test_auto_schedule*` 全改）
- [ ] **Step 5:**

```bash
cd backend && uv run pytest \
  tests/test_auto_schedule_time.py tests/test_auto_schedule_repo.py \
  tests/test_auto_schedule_model.py tests/test_auto_schedule_task.py \
  tests/test_auto_schedule_poll.py tests/test_auto_schedule_enqueue.py \
  tests/test_auto_schedule_enqueue.py -v --tb=line
```

- [ ] **Step 6: Commit** `refactor(auto_schedule): 自动任务迁入 domains 并改用 AppError`

### Task 2: AutoScheduleService + 薄 router

**Files:**
- Create: `domains/auto_schedules/service.py`（若 Task 1 已含 CRUD 逻辑则仅拆 router）、`router.py`
- Replace: `api/v1/auto_schedules.py` → re-export

**Interfaces:** `AutoScheduleService` 承接现 router 的 CRUD + enabled toggle + delete；`validate_task_input` 的 `ValueError` → `ValidationFailed`；`_get_owned` 的 404 → `NotFound("任务不存在")`；无字段更新 → `ValidationFailed("没有需要更新的字段")`。Router 只 Depends + service 静态方法。

- [ ] **Step 1:** 把 `api/v1/auto_schedules.py` 行为迁入 `service.py`（若 Task 1 未含）+ 薄 `router.py`（路径/前缀不变）
- [ ] **Step 2:** router 零 `HTTPException` / 零 `Repository`
- [ ] **Step 3:**

```bash
(rg "HTTPException|Repository" app/domains/auto_schedules/router.py && exit 1 || echo ok)
wc -l app/domains/auto_schedules/router.py
uv run pytest tests/test_auto_schedules_api.py tests/test_auto_schedule_enqueue.py tests/test_auto_schedule_time.py -v
```

- [ ] **Step 4: Commit** `refactor(auto_schedule): API 迁入 domains 薄 router`

---

## Wave B — ops / jobs 路由与横切异常统一

### Task 3: ops.py + jobs.py 薄化（AppError）

**Files:**
- Modify: `api/v1/ops.py`、`api/v1/jobs.py`

**做法：**
- `api/v1/ops.py` 4 处 `HTTPException` → AppError：
  - 404 未知任务 → `NotFound("未知任务")`
  - 400 不可启用/不可执行 → `ValidationFailed(detail)`
  - 501 暂不支持 → `AppError(f"...")` + `exc.status_code = 501`
- `api/v1/jobs.py` 1 处 404 → `NotFound("任务不存在")`
- 删除 `from fastapi import HTTPException`
- 不搬 ops.py 到 domains（ops 属横切运维；保持 `api/v1` 薄 router 直调 `services/ops` 模块函数）；若迁移中 router 已足够薄则不改结构

- [ ] **Step 1:** ops.py / jobs.py HTTPException → AppError
- [ ] **Step 2:**

```bash
(rg "HTTPException" app/api/v1/ops.py app/api/v1/jobs.py && exit 1 || echo ok)
uv run pytest tests/test_ops_arq_worker.py tests/test_ops_job_kind.py \
  tests/test_ops_jobs_aggregate.py tests/test_ops_run_enqueue.py tests/test_ops_run_hints.py -v
```

- [ ] **Step 3: Commit** `refactor(ops): ops/jobs 路由改用 AppError 统一错误映射`

### Task 4: 清理 services/ops 死代码异常分支

**Files:**
- Modify: `services/ops/sync_universe.py`、`services/ops/sync_stock_industry.py`、`services/ops/auto_screen.py`

**做法：** 三处 `except HTTPException as exc:` 为死代码（被捕获函数已改抛 `UpstreamFailed`/AppError）：
- `except HTTPException` → `except AppError`，`exc.detail` → `exc.message`
- 删除 `from fastapi import HTTPException`
- 验证消息语义：`_format_screen_lines` 等消费方不受影响

- [ ] **Step 1:** 三处 except 改为 AppError
- [ ] **Step 2:**

```bash
uv run pytest tests/test_ops_sync_universe.py tests/test_ops_sync_stock_industry.py \
  tests/test_ops_auto_screen.py tests/test_ops_warm_market.py -v --tb=line
```

- [ ] **Step 3: Commit** `refactor(ops): 同步任务异常分支改用 AppError 消除死代码`

---

## Wave C — 收尾

### Task 5: domains README + 总回归

- [ ] **Step 1:** README「已迁入」追加 `auto_schedules`（Phase 5）
- [ ] **Step 2:**

```bash
cd backend && uv run pytest -q --tb=short
```

- [ ] **Step 3: Commit** `docs(domains): 标注 auto_schedules 域已迁入`

---

## Spec coverage

| 项 | Tasks |
|----|-------|
| auto_schedules 域 | 1–2 |
| ops/jobs 路由薄化 + 异常统一 | 3–4 |
| 文档 + 全量回归 | 5 |

## Out of scope

- ops/worker 拓扑重写（含 `worker/tasks*.py` 迁移到 domains，保留现状）
- 拆除兼容壳（Phase 6）
- 统一日志 / 请求上下文中间件（后续横切项）
- 改前端 / 算法重写

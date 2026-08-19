# 自动任务（用户自定义选股定时）设计

日期：2026-08-19

## 目标

在 Web 端新增「自动任务」模块：用户创建自己的选股任务（选择配方 + 每周哪几天 + 一天内多个时刻），到点自动跑配方选股，结果写入选股历史并推送到已配置的通知渠道；支持创建、编辑、删除、启用/暂停。

## 范围

### 首版包含

- 新表 `app.auto_schedule` 存储按用户隔离的自动任务
- 自动任务 CRUD + 启用/暂停 API（`/api/v1/auto-schedules`）
- 分钟级守护 job 扫描命中任务并入队 ARQ 执行（复用内嵌调度器）
- ARQ worker 侧执行选股配方、写 `screener_runs` 历史、更新任务上次运行信息、推送通知渠道
- 前端「自动任务」页面 + 侧边栏入口

### 首版不做

- 非选股动作（跑运维任务、跑回测、定时发消息）
- 仅交易日执行（只做星期几维度）
- 补跑错过的时刻
- 多用户共享任务 / 任务级推送渠道配置（沿用用户已配渠道）

## 数据模型

新表 `app.auto_schedule`（Postgres）：

| 字段 | 类型 | 约束/说明 |
|---|---|---|
| id | bigint | PK（自增） |
| user_id | uuid | NOT NULL，index，归属用户 |
| name | varchar(64) | NOT NULL，任务名 |
| recipe_id | varchar | NOT NULL，选股配方（`intraday_multi` / `post_close_multi` / `radar_leader` 等） |
| days_of_week | text | NOT NULL，星期范围/列表，如 `mon-fri`、`mon,wed,fri` |
| times | jsonb | NOT NULL，每日时刻列表，如 `["09:35","14:00"]` |
| enabled | boolean | NOT NULL，默认 true |
| last_run_at | text | NULL，上次执行时间 |
| last_message | text | NULL，上次执行结果摘要 |
| last_success | boolean | NULL，上次是否成功 |
| created_at | text | NOT NULL |
| updated_at | text | NOT NULL |

沿用现有 alembic 迁移风格，新迁移 `013_auto_schedule`。

## 后端

### 文件与职责

| 文件 | 职责 |
|---|---|
| `app/models/auto_schedule.py` | `AutoSchedule` 模型，注册进 `models/__init__.py` |
| `alembic/versions/013_auto_schedule.py` | 建表 + user_id 索引 |
| `app/schemas/auto_schedule.py` | `AutoScheduleOut` / `AutoScheduleCreate` / `AutoScheduleUpdate` |
| `app/services/ops/auto_schedule.py` | 任务 CRUD（归属校验）、时间匹配逻辑（`matches_now` / `parse` / `validate`）、`run_task` 执行 |
| `app/api/v1/auto_schedules.py` | CRUD + 启用/暂停 API，注册进 `api_router` |
| `app/services/ops/embedded_scheduler.py` | 新增守护 job `auto_schedule_poll`（每分钟，内部 job 不对外开关） |
| `app/services/ops/runners.py` | `needs_user_id` 支持新 job |
| `app/worker/tasks.py` | 处理 `auto_schedule.run` 入队执行 |

### API

- `GET /auto-schedules` — 当前用户任务列表（含上次运行信息）
- `POST /auto-schedules` — 创建（name / recipe_id / days_of_week / times 必填，校验配方存在、星期合法、时刻合法且非空无重复）
- `PATCH /auto-schedules/{id}` — 编辑（name / recipe_id / days_of_week / times，校验归属）
- `PATCH /auto-schedules/{id}/enabled` — 启用/暂停（校验归属）
- `DELETE /auto-schedules/{id}` — 删除（校验归属）

所有路由走 `get_current_user`，仅操作当前用户自己的任务。配方合法性复用 `get_builtin_recipe`。

### 调度守护（方案 B：分钟级轮询 + ARQ）

在 `embedded_scheduler.py` 增加固定守护 job `auto_schedule_poll`，cron 每分钟（`* * * * *`），不暴露在调度页可跑列表：

1. 读全表启用任务（`enabled = true`）
2. 对每个任务，判断「当前星期几是否命中 `days_of_week`」且「当前 `HH:MM` 是否命中 `times`」
3. 命中任务以稳定 job id `auto:{task_id}` 入队 ARQ（复用 `enqueue` 的进行中防重语义，同一任务同一分钟内不重复入队）
4. 不补跑历史错过的时刻（只命中当前分钟）

守护 job 本身复用 `scheduler_lock` 分布式锁；多实例同时轮询不会重复执行。

### ARQ worker 执行

新增 runner：`run_auto_schedule_task(task_id)`。

1. 读任务行；不存在或未启用则跳过
2. 复用 `run_recipe_screen` + 写 `screener_runs`（source 记 `auto_schedule`），`top_n` 用配方默认值
3. 更新任务行 `last_run_at` / `last_message` / `last_success`
4. 成功时复用 `deliver_text` 推送到该用户启用渠道（event_type `auto_schedule.{task_id}`）

### 错误处理

- 校验失败：非法配方 / 非法 `days_of_week` / 非法 `times` / 时刻为空或重复 → 400
- 执行失败：任务行记录 `last_success=false` 与错误消息，任务不自动暂停，下次命中继续尝试
- 推送失败仅记日志，不影响选股主流程
- 多实例同时命中同一任务：稳定 job id 防重，只入队一次

## 前端

| 文件 | 职责 |
|---|---|
| `frontend/src/api/autoSchedule.ts` | `autoScheduleApi`：list / create / update / setEnabled / remove |
| `frontend/src/views/AutoScheduleView.vue` | 任务列表 + 新建/编辑弹窗 + 启用/暂停 + 删除 |
| `frontend/src/components/AppShell.vue` | 侧边栏新增「自动任务」菜单 |
| `frontend/src/components/NavIcon.vue` | 新增 `auto-schedule` 图标 |
| `frontend/src/router/index.ts` | 新增 `/auto-schedule` 路由 |

页面形态：

- 头部说明 + 「新建任务」按钮
- 任务列表：名称、配方名、调度文案（如「周一·三·五 09:35、14:00」）、启用开关、上次运行信息、编辑/删除
- 新建/编辑弹窗：名称输入、配方下拉（复用 `builtinRecipes`）、每周星期几复选框（默认周一至周五）、时刻列表编辑器（可增删，按时间排序去重）
- 删除需二次确认

## 测试

- 后端单测：
  - 时间匹配函数（星期命中、时刻命中、排序、去重）
  - CRUD API（权限隔离——A 用户看不到/改不了 B 用户的任务；校验非法输入）
  - 守护轮询（命中入队、未命中不入队、禁用不执行）
  - 执行 runner（写历史、更新任务 meta、推送 mock 调用）
- 前端 `vue-tsc` + `eslint` 通过

## 非目标（防范围蔓延）

- 不做非选股动作
- 不做仅交易日执行（只做星期几）
- 不做补跑
- 不做任务级推送渠道选择（沿用用户已配渠道）

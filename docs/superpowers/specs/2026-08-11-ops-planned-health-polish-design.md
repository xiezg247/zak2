# Ops planned 透明化与健康面板打磨设计

日期：2026-08-11  
状态：已批准（方案 1：前端编排 + 后端 `job_kind`）  
范围：仅 zak2；在独立演进分支上继续；不改 zak / vnpy-*

## 背景

独立演进后 Ops 已具备 `status_label` / `run_hint`（可跑 / 独立进程 / 未实现），但：

- 25 个 job 平铺混排，planned 与可跑难区分  
- planned / `collect_quotes` 仍可点「启用」开关（易误导）  
- 健康区缺 `scheduler_lock` 卡片（smoke 已要求验收，前端未展示）  
- 前端 `Health` 类型未声明 `scheduler_lock` / `quote_collector`

产品路线近期待办 #2：Ops planned job 透明化与健康面板打磨。

## 目标

1. 健康区一眼可见调度锁配置与 Redis 依赖状态。  
2. 任务表按 `job_kind` **分组 + 筛选**，非可跑不可开关、不可异步执行（前端禁用 + API 400）。  
3. 保持现有可跑 job / collector 语义与文案方向不变。

## 非目标

- 不统一 toolbar 与表内执行入口（不做 D）  
- 不实现任何新 planned job  
- 不展示当前持有锁的 job 列表、不改锁 TTL 语义  
- 不重做 Ops 视觉体系  

## 决策摘要

| 项 | 选择 |
|----|------|
| 范围 | 任务表透明化 + 健康面板（A+B） |
| 任务呈现 | 默认分组 + 顶栏筛选（全部/可跑/独立进程/未实现） |
| 契约 | 新增 `job_kind: runnable \| process \| planned` |
| 健康 | 新增调度锁卡片；payload 可轻量加 `ok` |

---

## 1. 健康面板

### 现状

`GET /api/v1/ops/health` 已返回：

```json
"scheduler_lock": {
  "backend": "redis",
  "ttl_seconds": 1800,
  "key_prefix": "zak2:scheduler:lock:"
}
```

OpsView 未渲染；`frontend/src/api/ops.ts` 的 `Health` 类型缺字段。

### 改动

| 项 | 内容 |
|----|------|
| UI | 健康区新增卡片「调度锁」：主行 `Redis 锁 · TTL {ttl_seconds}s`；副行 `key_prefix` |
| 标红 | `!health.redis.ok`（或后端提供的 `scheduler_lock.ok === false`）时卡片 `bad` |
| 类型 | `Health` 补全 `scheduler_lock`、`quote_collector`（与现 payload 对齐） |
| 后端（可选） | `scheduler_lock.ok: bool` = Redis 可达；其余字段保持 |

布局：现有 card grid 增至 7 卡；不改其它卡语义。

---

## 2. 任务表：`job_kind`、分组、筛选、禁用

### 后端

`list_scheduler_jobs` / `SchedulerJobOut` 增加：

```text
job_kind: "runnable" | "process" | "planned"
```

映射：

| job_kind | 条件 | status_label（保留） | run_hint |
|----------|------|----------------------|----------|
| `runnable` | ∈ `RUNNABLE_JOB_IDS` | 可跑 | `null` |
| `process` | `job_id == "collect_quotes"` | 独立进程 | collector 启动说明 |
| `planned` | 其余 | 未实现 | `未实现：见 docs/product-roadmap.md` |

保留布尔 `runnable`（`job_kind == "runnable"`）。前端分组/筛选以 **`job_kind` 为准**。

**写路径守卫**（启用开关 PATCH / 异步执行 POST）：

- `job_kind` 为 `process` 或 `planned` → **HTTP 400**，文案区分「独立进程请启 collector」vs「未实现」  
- `runnable` 行为不变  

实现位置：与现 `ops` API 校验 `RUNNABLE_JOB_IDS` 的路径对齐（扩展为拒绝非 runnable；`collect_quotes` 本就不在 RUNNABLE）。

### 前端

**筛选**（默认 `全部`）：`全部 | 可跑 | 独立进程 | 未实现`  
对应 `job_kind`：全部 / `runnable` / `process` / `planned`。

**分组**：筛选后的列表仍按节渲染，顺序固定：

1. 可跑  
2. 独立进程  
3. 未实现  

空节不渲染。节标题可用 `status_label` 或固定中文。

**行内控件：**

| job_kind | 启用开关 | 操作列 |
|----------|----------|--------|
| runnable | 可操作 | 「异步执行」 |
| process | disabled | `status_label` + `title=run_hint` |
| planned | disabled | 同上 |

工具栏快捷按钮本刀不改集合（仍只点可跑 job）。

---

## 3. 测试与文档

### 测试

- `job_kind` 映射：`collect_quotes` → process；某 RUNNABLE → runnable；某 planned → planned  
- API：对 planned/process 的 enable/run → 400  
- 既有 `test_ops_run_hints` / scheduler defaults 保持绿（可断言新增字段）  
- 前端：可选对分组 computed 做轻量单测；否则 smoke 勾选  

### 文档

- `docs/smoke-checklist.md`：补筛选/分组、调度锁卡、非可跑不可开关  
- `docs/product-roadmap.md`：近期待办 #2 标为进行中或完成后勾掉  

---

## 验收

1. `/ops` 可见调度锁卡；Redis 不可用时状态可读  
2. 任务表可筛选；默认分组展示三类  
3. planned/process 前端不可启用/执行；API 400  
4. `collect_quotes` 为 process，hint 指向 collector  
5. 可跑 job 行为不回退；相关 pytest 绿  

## 风险

| 风险 | 对策 |
|------|------|
| 仅靠中文 label 分组易脆 | 使用 `job_kind` 枚举 |
| 前端禁用被绕过 | API 400 |
| 7 卡挤布局 | 沿用现 grid；小屏已有响应式 |

## 实现计划

批准本 spec 后另写：`docs/superpowers/plans/2026-08-11-ops-planned-health-polish.md`

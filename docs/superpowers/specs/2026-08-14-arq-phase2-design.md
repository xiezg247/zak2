# ARQ 二期：Ops 去重 / bars 互斥 + screener/backtest 迁入

日期：2026-08-14  
状态：已批准（方案 1；去重语义 A；范围 C；撞车 API 回 200+已有 id）  
范围：仅 zak2；不改 zak / vnpy-*  
前置：[`2026-08-14-arq-ops-jobs-design.md`](./2026-08-14-arq-ops-jobs-design.md)（一期已落地）

## 背景

一期后 Ops 已 enqueue 到 ARQ，但：

1. **稳定 `_job_id` 未用**：enqueue 后调度锁立即释放，同一 Ops job / bars 组可叠跑。  
2. **screener（4）与 backtest（2）** 仍在 API 进程 `ThreadPoolExecutor` + 内存 `JobStore`；`/jobs` 双源聚合。

## 目标

1. **全部 Ops RUNNABLE**：`_job_id = ops:{ops_job_id}`；在途则不再入队，API **200 返回已有 job_id**。  
2. **bars 三组**在 worker 内 Redis 互斥；抢不到锁则本任务失败（诚实 message），不叠跑。  
3. **screener + backtest** 全部迁 ARQ；去掉对应线程池；**删除内存 JobStore**（及 `/jobs` 内存分支）。  
4. 前端 `pollJob` 契约不变：`GET /jobs/{id}` → `JobOut`，成功时 `result_ref` 为 run id。  
5. `./scripts/check.sh` 绿。

## 非目标

- 多 queue / Celery / 改前端轮询协议或间隔  
- quote-collector 改 ARQ  
- bars 抢锁失败的自动重试 / 死信 UI  
- screener/backtest 的 `_job_id` 去重（每次运行新 id，允许并行）

## 决策摘要

| 项 | 选择 |
|----|------|
| 总体方案 | 1：同队列扩展 worker + 通用旁路 |
| Ops 去重 | 稳定 `_job_id`；在途返回已有 id |
| 去重范围 | C：每个 Ops job 各自去重 + bars 组 worker 互斥 |
| 撞车 API | A：`200` + 已有 `job_id` |
| JobStore | 删除；状态只走 ARQ + 旁路 |

---

## 1. Ops：稳定 `_job_id` 与「可再次入队」

### 1.1 标识

```text
_job_id = f"ops:{ops_job_id}"   # 例 ops:sync_universe
```

ARQ 返回的 `job.job_id` 即为该稳定 id（对外 `JobAccepted.job_id`）。

### 1.2 在途判定（必须）

ARQ 在 **job key 或 result key 仍存在** 时 `enqueue_job(..., _job_id=...)` 会返回 `None`。若任务已 **complete** 但 result 未过期，会误挡下一次执行。

**唯一规则：**

1. 查 `Job(ops:{id}).status()`：  
   - `queued` | `deferred` | `in_progress` → **在途**：不入队，返回该 id（并确保旁路 meta 存在）。  
   - `complete` | `not_found` → **允许新跑**：若存在 result/job 残留 key，先删除（或 `abort_job`/等价清理），再 `enqueue_job(..., _job_id=ops:{id})`。  
2. 若 `enqueue` 仍返回 `None`（竞态）：再读一次 status；在途则返回已有 id，否则报错。

定时路径 `enqueue_ops_job_sync` 同样遵守；撞车时记 info 日志并返回已有 id（不视为调度失败）。

### 1.3 API

`POST /ops/scheduler/jobs/{job_id}/run`：始终 `200` + `JobAccepted(job_id=<ops:{job_id}>, kind=ops.{job_id})`（新入队或已在途）。

---

## 2. Worker：bars 互斥

### 2.1 集合（与一期调度一致）

```text
BARS_JOBS = {fill_watchlist_bars, batch_fill_stale, batch_download_universe}
```

### 2.2 锁

- Redis key：`zak2:arq:lock:bars`（`SET NX` + TTL，建议与 `scheduler_lock_ttl_seconds` 同量级或复用 settings）。  
- `run_ops_job` 在执行 runner **之前**：若 `ops_job_id in BARS_JOBS`，尝试抢锁；失败则返回 `{success: False, skipped: False, message: "bars 任务互斥：已有同类任务在执行"}`（或 raise 记 ARQ failed——**首期用返回 dict + success=False**，与 JobOut 映射一致）。  
- 成功抢锁：`try/finally` 中执行 runner 并释放锁（比对 token）。

非 bars Ops 不抢此锁。

### 2.3 与调度锁关系

调度侧短锁（enqueue 窗口）**保留**；真正防叠跑靠 `_job_id` + worker bars 锁。不在本期用 ARQ 唯一键替代 `scheduler_lock` 全链路。

---

## 3. Screener / Backtest 迁 ARQ

### 3.1 任务函数（worker）

将今日 `_run_*_job` 逻辑迁入 `app/worker/`（可分 `tasks_screener.py` / `tasks_backtest.py`），签名示意：

```python
async def run_screener_condition(ctx, *, user_id: str, body: dict) -> dict
# 返回 {success, result_ref?, error?, message?}
```

同类：`run_screener_recipe` / `run_screener_pattern` / `run_screener_reference_peer` / `run_backtest_single` / `run_backtest_batch`。

- 同步 DB 逻辑：`asyncio.to_thread`。  
- **不再**写 `job_store`；进度靠 ARQ status（无细粒度 progress 时：running=0.5，终态 1.0——与一期 Ops 映射一致）。batch 进度降级可接受。  
- `result_ref`：成功时仍为 screener/backtest **run id**（batch 可为 `last_id` 或 `batch_id`，与今日一致）。

`WorkerSettings.functions` 注册上述函数 + 现有 `run_ops_job`。`max_jobs` 可保持 2 或调至 3（文档说明即可）。

### 3.2 API

`screener.py` / `backtest.py`：

- 删除 `_executor` 与 `job_store` 引用。  
- `async` 入队：`enqueue_job("run_screener_condition", ...)`，**不**传稳定 `_job_id`。  
- 返回 `JobAccepted(job_id=arq_id)`；backtest batch 仍带 `batch_id`（可放 enqueue kwargs + 旁路 meta）。

### 3.3 旁路索引（统一）

将一期仅 Ops 的索引升级为**通用 jobs 索引**（或并行写入后切读）：

| Key | 用途 |
|-----|------|
| `zak2:arq:jobs:recent` | ZSET，member=arq_id |
| `zak2:arq:jobs:meta:{arq_id}` | HASH：`kind`, `created_at`, `user_id`, 可选 `ops_job_id` / `batch_id` |

Ops 入队也写入此统一索引；**废弃后**可读兼容旧 `zak2:arq:ops:*` 一版（或一次性双写再删旧 key 常量）。推荐：**双写一期**，`/jobs` 只读新索引；下个小清理可删旧常量。

`kind` 示例：`ops.sync_universe`、`screener.condition`、`backtest.batch`。

### 3.4 `/jobs`

- `get` / `list` **仅**旁路 + ARQ（不再读 `job_store`）。  
- 删除 `backend/app/jobs/store.py`（及包导出）；测试改为 mock ARQ/旁路。

---

## 4. 文件触点（预期）

| 路径 | 变更 |
|------|------|
| `backend/app/services/ops_enqueue.py`（可重命名/拆 `arq_jobs.py`） | `_job_id` 逻辑、清理 complete、统一索引、screener/backtest enqueue |
| `backend/app/worker/tasks.py`（+ screener/backtest modules） | bars 锁；新 task 函数 |
| `backend/app/worker/settings.py` | 注册 functions |
| `backend/app/api/v1/ops.py` | 撞车 200 已有 id |
| `backend/app/api/v1/screener.py` / `backtest.py` | enqueue；去线程池 |
| `backend/app/api/v1/jobs.py` | 去掉 JobStore |
| `backend/app/core/redis_keys.py` | bars 锁、统一 jobs 索引常量 |
| `backend/app/jobs/` | 删除 store |
| `backend/tests/...` | 去重、bars 锁、screener/backtest enqueue、jobs 聚合 |

---

## 5. 验收

1. 连续两次 `POST .../ops/.../run` 同一 job → 相同 `job_id`；worker 日志仅一次执行（在途期间）。  
2. 任务 **完成后** 可再次 run（新执行；id 仍为 `ops:{id}`）。  
3. 并行触发两个不同 bars job → 第二个 success=False 或排队后互斥失败 message（首期允许失败）。  
4. screener/backtest 提交 → 轮询 `/jobs/{id}` 至 success，`result_ref` 可用。  
5. 进程内无 screener/backtest/ops 的 `ThreadPoolExecutor`；无 `job_store` 引用。  
6. `./scripts/check.sh` 通过。

---

## 6. 风险

| 风险 | 缓解 |
|------|------|
| complete 后 `_job_id` 挡死 | §1.2 显式清理后再入队 |
| bars 锁 TTL 过短任务被抢 | TTL ≥ 现有 scheduler lock；持有者续期不做（首期） |
| `max_jobs=2` 下选股与 Ops 争用 | 可调高；监控队列延迟 |
| batch 无细粒度 progress | 文档接受；前端仍靠终态 |

## 修订相对一期

一期「enqueue 后锁释放可重复入队」的风险项由本设计关闭；「screener/backtest 仍用 JobStore」关闭。

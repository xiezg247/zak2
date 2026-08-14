# Ops 任务引入 ARQ 设计

日期：2026-08-14  
状态：已批准（方案 1：APScheduler enqueue + 独立 arq-worker；`/jobs` 聚合）  
范围：仅 zak2；不改 zak / vnpy-*

## 背景

Ops 定时与「立即执行」今日跑在 API 进程内：

- 内嵌 APScheduler 直接调用 `RUNNERS`
- `POST /ops/scheduler/jobs/{job_id}/run` 经 `ThreadPoolExecutor(max_workers=2)` + 内存 `JobStore`

重同步 / bars fill 与 uvicorn 同进程争资源；API 重启丢失内存 job 状态；多副本无法共享 deferred 执行。Redis 已存在（行情 / 调度锁），适合作为 ARQ broker。

历史文档曾写「不引入 arq/Celery」——那是当时薄做实范围约束；本设计**明确推翻该约束**，仅针对 Ops 执行路径。

## 目标

1. Ops 定时与手动「立即执行」在独立 **arq-worker** 中跑 `RUNNERS`，API 只负责校验与 enqueue。  
2. 保留内嵌 APScheduler 的 cron / 开关 / Redis 分布式锁 / bars 互斥；到点改为 enqueue。  
3. Ops 任务状态以 ARQ result 为准；`/jobs` 聚合 ARQ(ops) ∪ 内存 JobStore(screener/backtest)。  
4. `docker-compose` 增加 `arq-worker`；本地/CI 可跑通立即执行与状态查询。  
5. `./scripts/check.sh` 绿；现有 Ops API 契约（`JobAccepted.job_id`）保持可用。

## 非目标

- screener / backtest 迁 ARQ（仍用线程池 + 内存 JobStore）  
- 去掉 APScheduler 或改用 ARQ cron  
- 用 ARQ 唯一键替换 `scheduler_lock` / 进程内 bars 互斥  
- quote-collector 改 ARQ  
- 多 queue、复杂 retry/死信 UI、Celery  
- 改 zak / vnpy-*

## 决策摘要

| 项 | 选择 |
|----|------|
| 首期范围 | 仅 Ops RUNNERS（定时 + 立即执行） |
| 定时 | 保留 APScheduler → enqueue ARQ |
| 状态 | Ops → ARQ；screener/backtest → JobStore；`/jobs` 聚合 |
| Broker | 现有 `REDIS_URL`（与行情同实例，ARQ 用独立 key 前缀） |
| 部署 | compose 新增 `arq-worker` 服务 |

---

## 1. 架构

```text
Vue / Ops UI
    │
    ▼
FastAPI (api)
    ├── APScheduler（cron 触发）──► enqueue_ops_job ──► Redis (ARQ)
    ├── POST .../scheduler/jobs/{id}/run ─────────────► Redis (ARQ)
    └── GET /jobs ──► JobStore ∪ ARQ results

arq-worker
    └── run_ops_job(ctx, ops_job_id, user_id?, force?)
            └── RUNNERS[ops_job_id](db, ...)
            └── save_job_run_meta（沿用现有）
```

`quote-collector` 与行情 Redis key 不变；ARQ 使用库默认 job/result key（与 `zak2:*` 行情前缀不冲突）。

---

## 2. 依赖与配置

### 2.1 依赖

- `backend/pyproject.toml` 增加 `arq`（版本随 uv 解析，锁定到 `uv.lock`）。

### 2.2 Settings

在现有 settings 中增加（或复用）至少：

| 键 | 说明 |
|----|------|
| `REDIS_URL` | 已有；ARQ `RedisSettings.from_dsn` |
| `ARQ_QUEUE_NAME` | 可选，默认 `zak2:arq` 或 arq 默认 `arq:queue`；须 API 与 worker 一致 |

不强制新环境变量也可工作（全用默认 + `REDIS_URL`）；若用自定义 queue name，写入 `.env.example`。

### 2.3 Worker 入口

- 模块：`backend/app/worker/settings.py`，导出 `WorkerSettings`  
- `functions = [run_ops_job]`（定义于同包 `tasks.py`），`redis_settings` 来自 `REDIS_URL`  
- compose / 本地：`arq app.worker.settings.WorkerSettings`

---

## 3. 任务函数与 enqueue

### 3.1 `run_ops_job`

签名示意：

```python
async def run_ops_job(
    ctx: dict,
    ops_job_id: str,
    *,
    user_id: str | None = None,
    force: bool = False,
) -> dict:
```

行为：

1. 校验 `ops_job_id in RUNNABLE_JOB_IDS`（及现有 runner 存在）。  
2. 开 `SessionLocal()`，按现有 `ops.py` / `embedded_scheduler` 规则调用 `RUNNERS`（含 `needs_user_id`、`bilibili` 的 `force`）。  
3. 返回与今日 runner 一致的 `dict`（含 `success` / `message` 等）；异常则让 ARQ 记失败。  
4. **同步 runner**：用 `asyncio.to_thread` 或短生命周期线程跑同步 DB 逻辑，避免阻塞 event loop 过久；首期允许简单 `to_thread` 包一层。

### 3.2 `enqueue_ops_job`

- 供 API 与 embedded_scheduler 调用。  
- 返回 ARQ job id（字符串），作为对外 `JobAccepted.job_id`。  
- kind 约定：查询侧将 ARQ 任务映射为 `ops.{ops_job_id}`，与今日 `job_store.create(f"ops.{job_id}")` 一致。

### 3.3 立即执行路径

`POST /ops/scheduler/jobs/{job_id}/run`：

1. 保留现有权限 / `job_id` 校验 / catalog 检查。  
2. 去掉 `_executor.submit`；改为 `enqueue_ops_job`。  
3. 返回 `JobAccepted(job_id=<arq_id>, kind=f"ops.{job_id}")`。

可删除 Ops 专用 `ThreadPoolExecutor`（若文件内无其它用途）。

### 3.4 定时路径

`embedded_scheduler._run_job`：

1. **保留**：scheduler 总开关、进程内锁、bars 互斥、`scheduler_lock.try_acquire`、enabled 检查、`SCHEDULER_SCREEN_USER_ID` 检查。  
2. **变更**：通过检查后不再本地 `runner(db)`，改为 `enqueue_ops_job`；enqueue 成功即记日志。  
3. **锁释放时机（重要）**：  
   - **首期**：enqueue 成功后即可释放 Redis 锁与进程内锁（避免长任务占满 TTL，导致「锁过期但任务仍在跑」的假互斥）。  
   - bars 互斥：enqueue 后即从 `_running` 移除；**真正并行防重**依赖「同 job 勿重复 enqueue」——首期接受「锁窗口缩短到 enqueue 瞬间」；若需「同 bars job 在 worker 内互斥」，二期再加 worker 侧锁或 ARQ `_job_id`。  
4. bilibili 定时仍传 `force=False`；手动 run 传 `force=True`（与今日一致）。

> 自审注：锁在 enqueue 后释放意味着短时间可再次 enqueue 同一 job。首期用 ARQ `max_jobs` + 文档说明；二期可用稳定 `_job_id=f"ops:{job_id}"` 做去重（需评估与手动并发强制跑的产品语义）。

---

## 4. `/jobs` 聚合

### 4.1 现状

- `GET /jobs`、`GET /jobs/{id}` 只读内存 `job_store`。  
- Ops 最近任务列表（若有）也滤 `kind.startswith("ops.")`。

### 4.2 目标行为

| 来源 | kind | 状态来源 |
|------|------|----------|
| screener / backtest | 非 `ops.*` 或既有 kind | 内存 JobStore |
| Ops | `ops.{ops_job_id}` | ARQ job / result |

**get_by_id**：

1. 先查 `job_store.get(id)`；命中则返回。  
2. 再查 ARQ（`Job.from_id` / result store）；映射为 `JobOut`。  
3. 皆无 → 404。

**list_recent**（唯一方案，不依赖 ARQ 内部 list）：

1. **enqueue 时**写入 Redis 旁路索引：ZSET `zak2:arq:ops:recent`（score=enqueue unix ms，member=arq_id）；旁路 HASH `zak2:arq:ops:meta:{arq_id}` 存 `kind`、`ops_job_id`、`created_at`（可选 `user_id`）。保留最近 N 条（如 100），ZREMRANGEBYRANK 裁剪。  
2. **list**：读 JobStore recent ∪ 旁路 ZSET 成员；对旁路 id hydrate ARQ 状态后映射 `JobOut`；合并按 `created_at` 降序，截断 limit。  
3. **get_by_id**：先 JobStore，再旁路/ARQ；皆无 → 404。  

不把 Ops 状态写回内存 JobStore；不建 PG 表。

**JobOut 映射**：

| JobOut | ARQ |
|--------|-----|
| id | arq job id |
| kind | `ops.{ops_job_id}`（enqueue 时写入 job 参数或旁路） |
| status | pending/queued→`pending`；in_progress→`running`；complete→`success`/`failed` 依 result |
| progress | 无细粒度则 running=0.5，终态 1.0 或 0 |
| error | 异常信息 |
| result_ref | result.message 或 JSON 摘要 |
| created_at / updated_at | ARQ enqueue / finish 时间（ISO） |

---

## 5. Docker / 本地

### 5.1 compose

新增服务 `arq-worker`：

- 同 `api` 镜像与 `env_file`  
- `DATABASE_URL` / `REDIS_URL` 同 api  
- `depends_on`: postgres healthy, redis healthy（可不依赖 api healthy，避免环）  
- `restart: unless-stopped`  
- entrypoint：`arq app....WorkerSettings`

### 5.2 文档

- `README` / `.env.example`：说明需起 worker，否则 Ops 立即执行会一直排队。  
- 本地非 docker：`cd backend && arq app....WorkerSettings`。

---

## 6. 测试与验收

### 6.1 自动化

- 单元：enqueue 封装 mock Redis；`run_ops_job` 对假 runner / 未知 job_id。  
- 若有现成 Ops run 测试：改为断言调用 enqueue 而非 thread pool。  
- `./scripts/check.sh` 通过。

### 6.2 手动验收

1. `docker compose up` 含 `arq-worker`。  
2. Ops 立即执行某轻量 job → 返回 job_id → worker 日志有执行 → `GET /jobs/{id}` 终态 success/failed。  
3. API 进程 CPU/线程不再长时间跑该 runner。  
4. screener/backtest 异步任务行为与 `/jobs` 查询不变。  
5. 定时：临时 enable 一 job 或触发 scheduler 路径，确认 enqueue 而非本地执行（日志）。

---

## 7. 风险与后续

| 风险 | 缓解 |
|------|------|
| enqueue 后锁释放 → 重复入队 | 文档 + 二期 `_job_id` 去重 / worker 侧锁 |
| 同步 runner 阻塞 ARQ loop | `asyncio.to_thread`；`max_jobs` 调小（如 1–2） |
| Redis 与行情同实例 | ARQ key 前缀隔离；监控内存 |
| list 不完整 | 旁路 ZSET 索引 |

**二期候选**：screener/backtest 迁 ARQ；worker 侧 bars 互斥；稳定 `_job_id`；去掉 API 内嵌执行残留。

---

## 8. 文件触点（预期）

| 路径 | 变更 |
|------|------|
| `backend/pyproject.toml` / `uv.lock` | 加 arq |
| `backend/app/worker/settings.py` | `WorkerSettings` |
| `backend/app/worker/tasks.py` | `run_ops_job` |
| `backend/app/services/ops_enqueue.py` | enqueue + Redis 旁路索引 |
| `backend/app/services/embedded_scheduler.py` | 执行 → enqueue |
| `backend/app/api/v1/ops.py` | 去掉 thread pool；enqueue |
| `backend/app/api/v1/jobs.py` | 聚合查询 |
| `docker-compose.yml` | `arq-worker` |
| `.env.example` / README | 运维说明 |
| `backend/tests/...` | 覆盖 enqueue / 映射 |

---

## 修订说明

相对旧 spec「不引入 arq/Celery」：本文件批准后，**Ops 执行路径以 ARQ 为准**；其它子系统仍可不引入，直至单独设计。

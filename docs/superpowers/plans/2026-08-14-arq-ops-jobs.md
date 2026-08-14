# Ops 任务引入 ARQ Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ops 定时与立即执行改为 ARQ worker 跑 `RUNNERS`；API 只 enqueue；`/jobs` 聚合 ARQ(ops) 与内存 JobStore。

**Architecture:** 保留内嵌 APScheduler（cron/开关/锁）；到点与 `POST .../run` 调用 `enqueue_ops_job`；独立 `arq-worker` 执行 `run_ops_job`；Redis ZSET 旁路索引支撑 list。

**Tech Stack:** FastAPI、ARQ、Redis、APScheduler、pytest、Docker Compose

**Spec:** `docs/superpowers/specs/2026-08-14-arq-ops-jobs-design.md`

## Global Constraints

- 只改 zak2；不改 zak / vnpy-*
- 首期仅 Ops RUNNERS；screener/backtest 仍用内存 JobStore
- 保留 APScheduler + `scheduler_lock`；enqueue 成功后释放锁（见 spec）
- Broker 用现有 `REDIS_URL`；queue name 固定 `zak2:arq`
- commit message 简体中文：`<type>(<scope>): <简述>`
- `./scripts/check.sh` 最终必须绿

## File map

| 路径 | 职责 |
|------|------|
| `backend/pyproject.toml` / `uv.lock` | 加 `arq` |
| `backend/app/core/settings.py` | `arq_queue_name`（可选） |
| `backend/app/core/redis_keys.py` | ARQ 旁路 key 常量 |
| `backend/app/services/ops_enqueue.py` | enqueue + 旁路索引 + JobOut 映射 |
| `backend/app/worker/__init__.py` | 包 |
| `backend/app/worker/tasks.py` | `run_ops_job` |
| `backend/app/worker/settings.py` | `WorkerSettings` |
| `backend/app/api/v1/ops.py` | 去掉 thread pool；enqueue |
| `backend/app/services/embedded_scheduler.py` | 本地 runner → enqueue |
| `backend/app/api/v1/jobs.py` | 聚合 get/list |
| `docker-compose.yml` | `arq-worker` |
| `.env.example` / `README.md` | 运维说明 |
| `backend/tests/test_ops_enqueue.py` | enqueue / 旁路 / 映射 |
| `backend/tests/test_ops_arq_worker.py` | `run_ops_job` |
| `backend/tests/test_ops_jobs_aggregate.py` | `/jobs` 聚合 |

---

### Task 1: 依赖 + Redis key + settings

**Files:**
- Modify: `backend/pyproject.toml`
- Modify: `backend/app/core/settings.py`
- Modify: `backend/app/core/redis_keys.py`
- Modify: `.env.example`（注释即可）

**Interfaces:**
- Produces: 依赖 `arq`；`Settings.arq_queue_name: str = "zak2:arq"`；常量 `ARQ_OPS_RECENT_ZSET`、`ARQ_OPS_META_KEY_FMT`

- [ ] **Step 1: 添加依赖**

在 `backend/pyproject.toml` 的 `dependencies` 中加入 `"arq>=0.26.0"`（与现有 redis 兼容即可）。

```bash
cd backend && uv lock && uv sync --extra dev
```

Expected: `uv.lock` 含 `arq`；无错误。

- [ ] **Step 2: settings**

在 `Settings` 中增加：

```python
arq_queue_name: str = "zak2:arq"
```

- [ ] **Step 3: redis_keys**

在 `backend/app/core/redis_keys.py` 末尾追加：

```python
ARQ_OPS_RECENT_ZSET = f"{KEY_PREFIX}:arq:ops:recent"
ARQ_OPS_META_KEY_FMT = f"{KEY_PREFIX}:arq:ops:meta:{{job_id}}"
ARQ_OPS_RECENT_MAX = 100
```

- [ ] **Step 4: .env.example**

在 `REDIS_URL` 附近加注释：

```bash
# ARQ worker 与 API 共用 REDIS_URL；队列名默认 zak2:arq（可覆盖 ARQ_QUEUE_NAME）
# ARQ_QUEUE_NAME=zak2:arq
```

- [ ] **Step 5: Commit**

```bash
git add backend/pyproject.toml backend/uv.lock backend/app/core/settings.py \
  backend/app/core/redis_keys.py .env.example
git commit -m "$(cat <<'EOF'
chore(arq): 引入 arq 依赖与队列配置键

为 Ops 任务队列铺垫 REDIS 旁路常量与 queue name。
EOF
)"
```

---

### Task 2: `ops_enqueue`（enqueue + 旁路 + 状态映射）

**Files:**
- Create: `backend/app/services/ops_enqueue.py`
- Create: `backend/tests/test_ops_enqueue.py`

**Interfaces:**
- Consumes: `get_settings().redis_url` / `arq_queue_name`；`ARQ_OPS_*` keys；`redis.Redis`
- Produces:
  - `async def enqueue_ops_job(ops_job_id: str, *, user_id: str | None = None, force: bool = False) -> str`
  - `def enqueue_ops_job_sync(...) -> str`（`asyncio.run` 包装，供 APScheduler / 同步路由）
  - `async def get_ops_job_out(job_id: str) -> JobOut | None`
  - `async def list_ops_job_outs(*, limit: int = 50) -> list[JobOut]`
  - 旁路：`_index_ops_job(client, arq_id, ops_job_id, ...)`

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_ops_enqueue.py
from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.schemas.screener import JobOut
from app.services import ops_enqueue as m


def test_index_ops_job_writes_zset_and_hash() -> None:
    client = MagicMock()
    m._index_ops_job(
        client,
        arq_id="abc123",
        ops_job_id="sync_universe",
        user_id="u1",
        created_at="2026-08-14T03:00:00+00:00",
        score_ms=1_723_600_000_000,
    )
    client.zadd.assert_called_once()
    client.hset.assert_called_once()
    client.zremrangebyrank.assert_called_once()


@pytest.mark.asyncio
async def test_enqueue_ops_job_returns_arq_id_and_indexes() -> None:
    fake_job = MagicMock()
    fake_job.job_id = "jid-1"
    fake_pool = AsyncMock()
    fake_pool.enqueue_job = AsyncMock(return_value=fake_job)
    redis_sync = MagicMock()

    with (
        patch.object(m, "_arq_pool", AsyncMock(return_value=fake_pool)),
        patch.object(m, "_sync_redis", return_value=redis_sync),
        patch.object(m, "_index_ops_job") as idx,
    ):
        out = await m.enqueue_ops_job("sync_universe", user_id="u1", force=False)

    assert out == "jid-1"
    fake_pool.enqueue_job.assert_awaited_once()
    kwargs = fake_pool.enqueue_job.await_args.kwargs
    assert kwargs.get("ops_job_id") == "sync_universe" or (
        fake_pool.enqueue_job.await_args.args[0] == "run_ops_job"
    )
    idx.assert_called_once()


@pytest.mark.asyncio
async def test_map_complete_success_to_job_out() -> None:
    info = MagicMock()
    info.success = True
    info.result = {"success": True, "message": "ok"}
    info.enqueue_time = datetime(2026, 8, 14, 3, 0, 0, tzinfo=UTC)
    info.finish_time = datetime(2026, 8, 14, 3, 1, 0, tzinfo=UTC)

    out = m._job_out_from_arq(
        job_id="jid-1",
        ops_job_id="sync_universe",
        status_name="complete",
        result_info=info,
        created_at_fallback="2026-08-14T03:00:00+00:00",
    )
    assert isinstance(out, JobOut)
    assert out.id == "jid-1"
    assert out.kind == "ops.sync_universe"
    assert out.status == "success"
    assert out.result_ref == "ok"
```

- [ ] **Step 2: 跑测试确认失败**

```bash
cd backend && uv run pytest tests/test_ops_enqueue.py -v
```

Expected: FAIL（模块或符号不存在）。

- [ ] **Step 3: 实现 `ops_enqueue.py`**

要点（实现须满足测试；细节可微调但接口名固定）：

```python
# backend/app/services/ops_enqueue.py
from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

import redis
from arq import create_pool
from arq.connections import ArqRedis, RedisSettings
from arq.jobs import Job, JobStatus

from app.core.redis_keys import (
    ARQ_OPS_META_KEY_FMT,
    ARQ_OPS_RECENT_MAX,
    ARQ_OPS_RECENT_ZSET,
)
from app.core.settings import get_settings
from app.schemas.screener import JobOut

_pool: ArqRedis | None = None


def _sync_redis() -> redis.Redis:
    return redis.Redis.from_url(get_settings().redis_url, decode_responses=True)


async def _arq_pool() -> ArqRedis:
    global _pool
    if _pool is None:
        settings = get_settings()
        _pool = await create_pool(
            RedisSettings.from_dsn(settings.redis_url),
            default_queue_name=settings.arq_queue_name,
        )
    return _pool


def _index_ops_job(
    client: redis.Redis,
    *,
    arq_id: str,
    ops_job_id: str,
    user_id: str | None,
    created_at: str,
    score_ms: int,
) -> None:
    meta_key = ARQ_OPS_META_KEY_FMT.format(job_id=arq_id)
    client.zadd(ARQ_OPS_RECENT_ZSET, {arq_id: score_ms})
    client.hset(
        meta_key,
        mapping={
            "kind": f"ops.{ops_job_id}",
            "ops_job_id": ops_job_id,
            "created_at": created_at,
            "user_id": user_id or "",
        },
    )
    # 只保留最近 N 条：去掉更旧的
    client.zremrangebyrank(ARQ_OPS_RECENT_ZSET, 0, -(ARQ_OPS_RECENT_MAX + 1))


async def enqueue_ops_job(
    ops_job_id: str,
    *,
    user_id: str | None = None,
    force: bool = False,
) -> str:
    pool = await _arq_pool()
    job = await pool.enqueue_job(
        "run_ops_job",
        ops_job_id,
        user_id=user_id,
        force=force,
        _queue_name=get_settings().arq_queue_name,
    )
    if job is None:
        raise RuntimeError(f"enqueue 失败（可能重复 job id）：{ops_job_id}")
    now = datetime.now(UTC)
    created_at = now.isoformat()
    score_ms = int(now.timestamp() * 1000)
    _index_ops_job(
        _sync_redis(),
        arq_id=job.job_id,
        ops_job_id=ops_job_id,
        user_id=user_id,
        created_at=created_at,
        score_ms=score_ms,
    )
    return job.job_id


def enqueue_ops_job_sync(
    ops_job_id: str,
    *,
    user_id: str | None = None,
    force: bool = False,
) -> str:
    return asyncio.run(enqueue_ops_job(ops_job_id, user_id=user_id, force=force))


def _job_out_from_arq(
    *,
    job_id: str,
    ops_job_id: str,
    status_name: str,
    result_info: Any | None,
    created_at_fallback: str,
) -> JobOut:
    kind = f"ops.{ops_job_id}"
    created_at = created_at_fallback
    updated_at = created_at_fallback
    status = "pending"
    progress = 0.0
    error: str | None = None
    result_ref: str | None = None

    if status_name in {"queued", "deferred"}:
        status, progress = "pending", 0.0
    elif status_name == "in_progress":
        status, progress = "running", 0.5
    elif status_name == "complete":
        progress = 1.0
        if result_info is None:
            status = "failed"
            error = "无结果"
        elif not getattr(result_info, "success", False):
            status = "failed"
            error = str(getattr(result_info, "result", "failed"))
        else:
            raw = getattr(result_info, "result", None)
            if isinstance(raw, dict):
                ok = True if ops_job_id == "purge_stale_cache" else bool(raw.get("success", True))
                msg = str(raw.get("message") or "完成")
                if raw.get("skipped") or ok:
                    status, result_ref = "success", msg
                else:
                    status, error = "failed", msg
            else:
                status, result_ref = "success", str(raw)
        if result_info is not None:
            if getattr(result_info, "enqueue_time", None):
                created_at = result_info.enqueue_time.astimezone(UTC).isoformat()
            if getattr(result_info, "finish_time", None):
                updated_at = result_info.finish_time.astimezone(UTC).isoformat()
    elif status_name == "not_found":
        status, error = "failed", "任务不存在"

    return JobOut(
        id=job_id,
        kind=kind,
        status=status,
        progress=progress,
        error=error,
        result_ref=result_ref,
        created_at=created_at,
        updated_at=updated_at,
    )


async def get_ops_job_out(job_id: str) -> JobOut | None:
    client = _sync_redis()
    meta_key = ARQ_OPS_META_KEY_FMT.format(job_id=job_id)
    meta = client.hgetall(meta_key)
    ops_job_id = (meta or {}).get("ops_job_id")
    created_at = (meta or {}).get("created_at") or datetime.now(UTC).isoformat()
    if not ops_job_id:
        # 无旁路时仍尝试 ARQ（可能仅知 id）
        ops_job_id = ""

    pool = await _arq_pool()
    job = Job(job_id, redis=pool, _queue_name=get_settings().arq_queue_name)
    st = await job.status()
    if st == JobStatus.not_found and not meta:
        return None
    info = await job.result_info()
    if not ops_job_id and info is not None:
        # kwargs 回退
        ops_job_id = str((info.kwargs or {}).get("ops_job_id") or "")
        if not ops_job_id and info.args:
            ops_job_id = str(info.args[0])
    if not ops_job_id:
        return None
    return _job_out_from_arq(
        job_id=job_id,
        ops_job_id=ops_job_id,
        status_name=st.name if hasattr(st, "name") else str(st),
        result_info=info,
        created_at_fallback=created_at,
    )


async def list_ops_job_outs(*, limit: int = 50) -> list[JobOut]:
    client = _sync_redis()
    ids = client.zrevrange(ARQ_OPS_RECENT_ZSET, 0, max(limit - 1, 0)) or []
    out: list[JobOut] = []
    for arq_id in ids:
        row = await get_ops_job_out(str(arq_id))
        if row is not None:
            out.append(row)
    return out[:limit]
```

注意：`enqueue_job` 第一个位置参数是函数名 `"run_ops_job"`，随后位置参数对应 `ops_job_id`；`user_id`/`force` 用关键字传入，与 Task 3 签名一致。

- [ ] **Step 4: 跑测试通过**

```bash
cd backend && uv run pytest tests/test_ops_enqueue.py -v
```

Expected: PASS。若 `JobStatus` 枚举 `.name` 与断言不一致，调整 `_job_out_from_arq` 的 `status_name` 比较为 `JobStatus` 枚举值。

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/ops_enqueue.py backend/tests/test_ops_enqueue.py
git commit -m "$(cat <<'EOF'
feat(arq): 实现 Ops 入队与 Redis 旁路索引

API/调度可 enqueue；状态可映射为 JobOut。
EOF
)"
```

---

### Task 3: Worker `run_ops_job` + `WorkerSettings`

**Files:**
- Create: `backend/app/worker/__init__.py`（可空）
- Create: `backend/app/worker/tasks.py`
- Create: `backend/app/worker/settings.py`
- Create: `backend/tests/test_ops_arq_worker.py`

**Interfaces:**
- Consumes: `RUNNERS`、`needs_user_id`、`ops_sync_bilibili_feed`、`SessionLocal`
- Produces:
  - `async def run_ops_job(ctx, ops_job_id: str, *, user_id: str | None = None, force: bool = False) -> dict`
  - `class WorkerSettings`（`functions`、`redis_settings`、`queue_name`、`max_jobs=2`）

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_ops_arq_worker.py
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.worker import tasks as t


@pytest.mark.asyncio
async def test_run_ops_job_unknown_raises() -> None:
    with pytest.raises(ValueError, match="未知"):
        await t.run_ops_job({}, "not_a_real_job")


@pytest.mark.asyncio
async def test_run_ops_job_calls_runner_in_thread() -> None:
    db = MagicMock()
    runner = MagicMock(return_value={"success": True, "message": "done"})
    with (
        patch("app.worker.tasks.SessionLocal", return_value=db),
        patch.dict("app.worker.tasks.RUNNERS", {"sync_universe": runner}, clear=False),
        patch("app.worker.tasks.needs_user_id", return_value=False),
    ):
        out = await t.run_ops_job({}, "sync_universe", user_id=None, force=False)
    assert out["success"] is True
    runner.assert_called_once_with(db)
    db.close.assert_called_once()


@pytest.mark.asyncio
async def test_run_ops_job_bilibili_respects_force() -> None:
    db = MagicMock()
    with (
        patch("app.worker.tasks.SessionLocal", return_value=db),
        patch("app.worker.tasks.ops_sync_bilibili_feed.sync_bilibili_feed") as sync_fn,
        patch("app.worker.tasks.ops_sync_bilibili_feed.JOB_ID", "sync_bilibili_feed"),
    ):
        sync_fn.return_value = {"success": True, "message": "feed"}
        await t.run_ops_job({}, "sync_bilibili_feed", force=False)
    sync_fn.assert_called_once_with(db, force=False)
```

- [ ] **Step 2: 跑测试确认失败**

```bash
cd backend && uv run pytest tests/test_ops_arq_worker.py -v
```

Expected: FAIL。

- [ ] **Step 3: 实现 tasks + settings**

```python
# backend/app/worker/tasks.py
from __future__ import annotations

import asyncio
from typing import Any

from app.core.db import SessionLocal
from app.services import ops_sync_bilibili_feed
from app.services.ops_catalog import RUNNABLE_JOB_IDS
from app.services.ops_runners import RUNNERS, needs_user_id


def _execute_sync(
    ops_job_id: str,
    *,
    user_id: str | None,
    force: bool,
) -> dict[str, Any]:
    if ops_job_id not in RUNNABLE_JOB_IDS or ops_job_id not in RUNNERS:
        raise ValueError(f"未知或不可执行任务: {ops_job_id}")
    db = SessionLocal()
    try:
        if ops_job_id == ops_sync_bilibili_feed.JOB_ID:
            return ops_sync_bilibili_feed.sync_bilibili_feed(db, force=force)
        runner = RUNNERS[ops_job_id]
        if needs_user_id(ops_job_id):
            if not (user_id or "").strip():
                raise ValueError(f"{ops_job_id} 需要 user_id")
            return runner(db, user_id=user_id)
        return runner(db)
    finally:
        db.close()


async def run_ops_job(
    ctx: dict,
    ops_job_id: str,
    *,
    user_id: str | None = None,
    force: bool = False,
) -> dict:
    _ = ctx
    return await asyncio.to_thread(
        _execute_sync, ops_job_id, user_id=user_id, force=force
    )
```

```python
# backend/app/worker/settings.py
from __future__ import annotations

from arq.connections import RedisSettings

from app.core.settings import get_settings
from app.worker.tasks import run_ops_job


class WorkerSettings:
    functions = [run_ops_job]
    max_jobs = 2

    @staticmethod
    def redis_settings() -> RedisSettings:
        return RedisSettings.from_dsn(get_settings().redis_url)

    # arq 读取类属性；用 property 不稳，在模块加载时绑定：
    queue_name = None  # 下方覆盖


_settings = get_settings()
WorkerSettings.queue_name = _settings.arq_queue_name
WorkerSettings.redis_settings = RedisSettings.from_dsn(_settings.redis_url)  # type: ignore[assignment]
```

**纠正：** ARQ 期望 `redis_settings` 为 `RedisSettings` 实例（或可调用）。落地用：

```python
class WorkerSettings:
    functions = [run_ops_job]
    max_jobs = 2
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
    queue_name = get_settings().arq_queue_name
```

`backend/app/worker/__init__.py` 可留空或导出 `WorkerSettings`。

- [ ] **Step 4: 跑测试通过**

```bash
cd backend && uv run pytest tests/test_ops_arq_worker.py tests/test_ops_enqueue.py -v
```

Expected: PASS。

- [ ] **Step 5: Commit**

```bash
git add backend/app/worker backend/tests/test_ops_arq_worker.py
git commit -m "$(cat <<'EOF'
feat(arq): 增加 run_ops_job 与 WorkerSettings

独立 worker 在线程中执行同步 RUNNERS。
EOF
)"
```

---

### Task 4: Ops 立即执行改 enqueue

**Files:**
- Modify: `backend/app/api/v1/ops.py`
- Modify: `backend/tests/test_ops_job_guards.py`（若断言 thread/job_store）
- Create 或 Modify: `backend/tests/test_ops_run_enqueue.py`

**Interfaces:**
- Consumes: `enqueue_ops_job`（async）或 `enqueue_ops_job_sync`
- Produces: `POST .../run` 返回 ARQ `job_id`；`GET /ops/jobs/recent` 读 `list_ops_job_outs`

- [ ] **Step 1: 写/改测试**

```python
# backend/tests/test_ops_run_enqueue.py
from __future__ import annotations

from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.main import app


def test_run_scheduler_job_enqueues(monkeypatch) -> None:
    # 复用项目既有 auth fixture 模式；若无则 patch get_current_user
    ...
```

更稳妥的最小测法（与现有 guards 风格对齐）：直接测 handler 逻辑或 patch 路由依赖。查看 `test_ops_job_guards.py` 的 client/auth 写法并照抄；核心断言：

```python
with patch("app.api.v1.ops.enqueue_ops_job", new_callable=AsyncMock) as enq:
    enq.return_value = "arq-id-1"
    # POST runnable job
    ...
    enq.assert_awaited()
    assert body["job_id"] == "arq-id-1"
```

- [ ] **Step 2: 改 `ops.py`**

1. 删除 `ThreadPoolExecutor`、`_run_ops_job`、对 `job_store` 的 Ops 写入。  
2. `run_scheduler_job` 改为 `async def`，校验后：

```python
arq_id = await enqueue_ops_job(job_id, user_id=str(user.id), force=True)
return JobAccepted(job_id=arq_id, kind=f"ops.{job_id}")
```

3. `list_ops_jobs` 改为 `async`，返回 `await list_ops_job_outs()`。

手动跑 bilibili：`force=True`（与今日 RUNNERS 一致）。

- [ ] **Step 3: 跑相关测试**

```bash
cd backend && uv run pytest tests/test_ops_run_enqueue.py tests/test_ops_job_guards.py -v
```

Expected: PASS。

- [ ] **Step 4: Commit**

```bash
git add backend/app/api/v1/ops.py backend/tests/test_ops_run_enqueue.py \
  backend/tests/test_ops_job_guards.py
git commit -m "$(cat <<'EOF'
feat(ops): 立即执行改为 ARQ 入队

去掉 API 进程内 Ops 线程池。
EOF
)"
```

---

### Task 5: 内嵌调度改为 enqueue

**Files:**
- Modify: `backend/app/services/embedded_scheduler.py`
- Create: `backend/tests/test_embedded_scheduler_enqueue.py`

**Interfaces:**
- Consumes: `enqueue_ops_job_sync`
- Produces: `_run_job` 在校验/加锁后 enqueue，然后释放锁；不再本地 `runner(db)`

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_embedded_scheduler_enqueue.py
from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.services import embedded_scheduler as es


def test_run_job_enqueues_instead_of_local_runner() -> None:
    settings = MagicMock()
    settings.scheduler_effective_enabled = True
    settings.scheduler_screen_user_id = ""

    with (
        patch.object(es, "get_settings", return_value=settings),
        patch.object(es.scheduler_lock, "try_acquire", return_value=True),
        patch.object(es.scheduler_lock, "release"),
        patch.object(es.scheduler_lock, "make_token", return_value="t"),
        patch.object(es, "SessionLocal") as SL,
        patch.object(es, "load_scheduler_config", return_value={"config": {"sync_universe": {"enabled": True}}}),
        patch.object(es, "enqueue_ops_job_sync", return_value="jid") as enq,
        patch.dict(es.RUNNERS, {"sync_universe": MagicMock()}, clear=False),
    ):
        SL.return_value = MagicMock()
        # 需要能拿到锁：清空 _running，确保 _locks 可 acquire
        with es._locks["sync_universe"]:
            pass  # 确保锁存在
        # 释放后调用
        es._run_job("sync_universe")
    enq.assert_called_once()
    assert enq.call_args.kwargs.get("force") is False
```

实现时按真实 `_run_job` 控制流微调 mock（enabled 检查、finally 释放锁）。关键断言：**调用了 `enqueue_ops_job_sync`，且未调用 `RUNNERS[...](db)`**。

- [ ] **Step 2: 改 `_run_job`**

在通过 enabled / user_id 检查后：

```python
from app.services.ops_enqueue import enqueue_ops_job_sync

user_id = None
force = False
if needs_user_id(job_id):
    user_id = (settings.scheduler_screen_user_id or "").strip()
    if not user_id:
        _logger.warning(...)
        return
if job_id == ops_sync_bilibili_feed.JOB_ID:
    force = False

arq_id = enqueue_ops_job_sync(job_id, user_id=user_id, force=force)
_logger.info("embedded scheduler enqueued %s -> %s", job_id, arq_id)
# 不要本地 runner；finally 仍 release 锁
```

删除本地 `runner(db)` / bilibili 本地调用块。`SessionLocal` 若仅用于 `load_scheduler_config`，可保留短会话。

- [ ] **Step 3: 跑测试**

```bash
cd backend && uv run pytest tests/test_embedded_scheduler_enqueue.py -v
```

Expected: PASS。

- [ ] **Step 4: Commit**

```bash
git add backend/app/services/embedded_scheduler.py \
  backend/tests/test_embedded_scheduler_enqueue.py
git commit -m "$(cat <<'EOF'
feat(scheduler): 定时 Ops 改为 ARQ 入队

APScheduler 只负责触发与抢锁，执行下沉到 worker。
EOF
)"
```

---

### Task 6: `/jobs` 聚合

**Files:**
- Modify: `backend/app/api/v1/jobs.py`
- Create: `backend/tests/test_ops_jobs_aggregate.py`

**Interfaces:**
- Consumes: `job_store`、`get_ops_job_out`、`list_ops_job_outs`
- Produces: get/list 合并两边

- [ ] **Step 1: 写测试**

```python
# backend/tests/test_ops_jobs_aggregate.py
from __future__ import annotations

from unittest.mock import AsyncMock, patch

from app.jobs.store import job_store
from app.schemas.screener import JobOut


@pytest.mark.asyncio
async def test_get_prefers_memory_then_arq() -> None:
    from app.api.v1 import jobs as jobs_api

    mem = job_store.create("backtest.x")
    with patch.object(jobs_api, "get_ops_job_out", new_callable=AsyncMock) as g:
        out = await jobs_api._resolve_job(mem.id)  # 若抽出 helper
    assert out.id == mem.id
    g.assert_not_called()
```

实现时可在 `jobs.py` 增加：

```python
async def _resolve_job(job_id: str) -> JobOut | None:
    job = job_store.get(job_id)
    if job:
        return _to_out(job)
    return await get_ops_job_out(job_id)
```

list：

```python
async def list_jobs(...):
    mem = [_to_out(j) for j in job_store.list_recent()]
    ops = await list_ops_job_outs(limit=50)
    merged = sorted(mem + ops, key=lambda j: j.created_at, reverse=True)
    return merged[:50]
```

端点改为 `async def`。

- [ ] **Step 2: 实现并跑测**

```bash
cd backend && uv run pytest tests/test_ops_jobs_aggregate.py -v
```

Expected: PASS。

- [ ] **Step 3: Commit**

```bash
git add backend/app/api/v1/jobs.py backend/tests/test_ops_jobs_aggregate.py
git commit -m "$(cat <<'EOF'
feat(jobs): 聚合内存 JobStore 与 ARQ Ops 状态

/jobs 可查询 Ops 入队任务终态。
EOF
)"
```

---

### Task 7: Docker Compose + 文档

**Files:**
- Modify: `docker-compose.yml`
- Modify: `README.md`
- Modify: `.env.example`（若 Task 1 未写全）

- [ ] **Step 1: 增加 `arq-worker` 服务**

放在 `quote-collector` 旁：

```yaml
  arq-worker:
    build:
      context: ./backend
      dockerfile: Dockerfile
    env_file:
      - .env
    environment:
      DATABASE_URL: postgresql+psycopg://zak2:zak2@postgres:5432/zak2
      REDIS_URL: redis://redis:6379/0
    entrypoint: ["arq", "app.worker.settings.WorkerSettings"]
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    restart: unless-stopped
```

更新文件头注释：`postgres + redis + api + arq-worker + quote-collector + web`。

- [ ] **Step 2: README**

- Compose 段落标题加入 `arq-worker`。  
- 本地启动增加：

```bash
# 另开：Ops ARQ worker（否则 Ops 立即执行会一直排队）
cd backend && uv run arq app.worker.settings.WorkerSettings
```

- [ ] **Step 3: Commit**

```bash
git add docker-compose.yml README.md .env.example
git commit -m "$(cat <<'EOF'
chore(compose): 增加 arq-worker 服务与启动说明

Ops 任务依赖独立 worker 消费队列。
EOF
)"
```

---

### Task 8: 全量验收

**Files:** 无新文件（修失败测试）

- [ ] **Step 1: check.sh**

```bash
./scripts/check.sh
```

Expected: `OK：测试与构建通过`。

- [ ] **Step 2: 手动冒烟（有 Docker 时）**

```bash
docker compose up --build -d
# 登录后 POST /api/v1/ops/scheduler/jobs/<轻量job>/run
# GET /api/v1/jobs/{job_id} 至 success/failed
# docker compose logs arq-worker --tail=50
```

- [ ] **Step 3: 若有失败则修复并追加 commit**（简体中文 message）

- [ ] **Step 4: 最终确认无残留**

- `ops.py` 无 Ops 用 `ThreadPoolExecutor`  
- `embedded_scheduler` 无本地 `RUNNERS[...](db)`（除测试 mock）  
- screener/backtest 仍用 `job_store`

---

## Spec coverage（自检）

| Spec 项 | Task |
|---------|------|
| 加 arq + queue name | 1 |
| enqueue + ZSET 旁路 | 2 |
| `run_ops_job` + WorkerSettings | 3 |
| 立即执行 enqueue | 4 |
| APScheduler → enqueue，锁 enqueue 后释放 | 5 |
| `/jobs` 聚合 | 6 |
| compose arq-worker + README | 7 |
| check.sh / 手动验收 | 8 |
| bilibili force 定时 False / 手动 True | 3+4+5 |
| 非目标：screener/backtest/quote-collector | 未改 |

## 执行注意

- FastAPI 同步路由若暂不改 async：可用 `enqueue_ops_job_sync`；优先 `async def` + `await enqueue_ops_job`。  
- `WorkerSettings.redis_settings` 必须是 ARQ 可识别的形式（实例，非 unbound 方法）。  
- 测试勿连真实 Redis：一律 mock `create_pool` / `_sync_redis` / `_arq_pool`。

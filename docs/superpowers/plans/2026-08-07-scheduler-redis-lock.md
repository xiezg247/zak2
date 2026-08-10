# 内嵌调度 Redis job 锁 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development（推荐）或 executing-plans。步骤用 `- [ ]` 跟踪。

**Goal:** 定时 job 经 Redis SET NX 抢锁，多 API 副本防双跑；Redis 不可用则跳过。

**Architecture:** `scheduler_lock` 封装 acquire/release → `_run_job` 在进程锁之后抢分布式锁 → health/settings/docs。

**Tech Stack:** redis-py、APScheduler（现有）、pytest + MagicMock。

**Spec:** `docs/superpowers/specs/2026-08-07-scheduler-redis-lock-design.md`

## Global Constraints

- 只改 zak2；不改 zak
- Redis 异常 → 跳过（不降级无锁执行）
- 仅 `embedded_scheduler._run_job` 加锁；Ops 手动立即执行不加分布式锁
- Commit 仅用户明确要求时（默认跳过）

---

## File map

| 文件 | 职责 |
|------|------|
| `backend/app/services/scheduler_lock.py` | token / TTL / try_acquire / release |
| `backend/app/services/embedded_scheduler.py` | `_run_job` 接入 |
| `backend/app/core/settings.py` | `scheduler_lock_ttl_seconds` |
| `backend/app/services/ops_health.py` | health 薄字段 |
| `backend/tests/test_scheduler_lock.py` | 锁单测 |
| `backend/tests/test_embedded_scheduler.py` | 未获锁不跑 runner |
| `.env.example` / `docs/gap-vs-desktop.md` / `docs/smoke-checklist.md` / README 若有调度说明 | 文档 |

---

### Task 1: scheduler_lock 模块 + 单测

**Files:**
- Create: `backend/app/services/scheduler_lock.py`
- Create: `backend/tests/test_scheduler_lock.py`
- Modify: `backend/app/core/settings.py`

**Interfaces:**
- `LOCK_KEY_PREFIX = "zak2:scheduler:lock:"`
- `DEFAULT_TTL = 1800`
- `clamp_ttl(seconds: int) -> int`  # [60, 7200]
- `lock_key(job_id: str) -> str`
- `make_token() -> str`
- `try_acquire(job_id, *, token, ttl=None, client=None) -> bool`
- `release(job_id, token, *, client=None) -> None`

Redis：`redis.Redis.from_url(get_settings().redis_url, decode_responses=True)`（可注入 client 便于测）。

Release Lua：

```lua
if redis.call("get", KEYS[1]) == ARGV[1] then
  return redis.call("del", KEYS[1])
else
  return 0
end
```

- [ ] **Step 1: 失败单测**

```python
from unittest.mock import MagicMock
from app.services import scheduler_lock as sl

def test_clamp_ttl() -> None:
    assert sl.clamp_ttl(10) == 60
    assert sl.clamp_ttl(1800) == 1800
    assert sl.clamp_ttl(99999) == 7200

def test_try_acquire_ok() -> None:
    client = MagicMock()
    client.set.return_value = True
    assert sl.try_acquire("purge_expired", token="t1", client=client) is True
    client.set.assert_called()  # NX EX

def test_try_acquire_busy() -> None:
    client = MagicMock()
    client.set.return_value = None
    assert sl.try_acquire("purge_expired", token="t1", client=client) is False

def test_try_acquire_redis_error() -> None:
    import redis
    client = MagicMock()
    client.set.side_effect = redis.RedisError("down")
    assert sl.try_acquire("purge_expired", token="t1", client=client) is False

def test_release_only_own_token() -> None:
    client = MagicMock()
    client.eval.return_value = 1
    sl.release("purge_expired", "t1", client=client)
    client.eval.assert_called_once()
```

- [ ] **Step 2–4: 实现 Settings 字段 + module；GREEN；Commit 跳过**

---

### Task 2: 接入 `_run_job` + health + 单测

**Files:**
- Modify: `backend/app/services/embedded_scheduler.py`
- Modify: `backend/app/services/ops_health.py`
- Modify: `backend/tests/test_embedded_scheduler.py`（或新建）

**`_run_job` 伪代码：**

```python
# after process lock acquired:
token = scheduler_lock.make_token()
if not scheduler_lock.try_acquire(job_id, token=token):
    _logger.info("embedded scheduler skip %s: distributed lock not acquired", job_id)
    # release process lock / running set; return
try:
    ... existing runner ...
finally:
    scheduler_lock.release(job_id, token)
    ... existing cleanup ...
```

Health 增加 `scheduler_lock` 字段（见 spec）。

- [ ] **单测：** patch `try_acquire` False → runner 不被调用；True → 调用且 finally release

- [ ] **Commit** — 跳过

---

### Task 3: 文档 + 全量

**Files:**
- `.env.example`
- `docs/gap-vs-desktop.md`
- `docs/smoke-checklist.md`
- README 若有「多副本双跑」表述则改为「Redis job 锁」

- [ ] **pytest 全量 + `npm run build`；Commit 跳过**

---

## Spec coverage

| Spec | Task |
|------|------|
| lock module + TTL settings | 1 |
| _run_job + health | 2 |
| docs + 验收 | 3 |

无 TBD。

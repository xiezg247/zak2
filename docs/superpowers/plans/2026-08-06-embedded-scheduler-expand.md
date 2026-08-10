# 内嵌调度扩到全部可跑 Job Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development（推荐）或 executing-plans。步骤用 `- [ ]` 跟踪。

**Goal:** 内嵌 APScheduler 调度全部 `RUNNABLE_JOB_IDS`，与 Ops 手动跑同源 runner；选股定时依赖 `SCHEDULER_SCREEN_USER_ID`。

**Architecture:** 抽出 `ops_runners.RUNNERS`；`bars_scheduler` 升格为 `embedded_scheduler`（默认 cron + 互斥 + 选股 user）；`list_scheduler_jobs` 合并默认 cron 供 Ops 只读展示。

**Tech Stack:** FastAPI、APScheduler、现有 ops_* runners、Vue Ops、pytest。

**Spec:** `docs/superpowers/specs/2026-08-06-embedded-scheduler-expand-design.md`

## Global Constraints

- 只改 zak2；不改 zak / vnpy-*
- 不做选主、不做 Web 改 cron UI、不做交易时段硬校验
- 生效总开关：`embedded_scheduler_enabled and bars_scheduler_enabled`
- Commit 仅在用户明确要求时执行（本仓库步骤默认跳过 commit）

---

## File map

| 文件 | 职责 |
|------|------|
| `backend/app/services/ops_runners.py` | `RUNNERS` 映射 + `SCREEN_JOB_IDS` |
| `backend/app/services/scheduler_defaults.py` | 默认 cron / 解析 hour·minute·dow·intraday hours |
| `backend/app/services/embedded_scheduler.py` | APScheduler 启停与 `_run_job` |
| `backend/app/services/bars_scheduler.py` | 删除或薄 re-export（推荐删除，改 main） |
| `backend/app/core/settings.py` | 新字段 |
| `backend/app/api/v1/ops.py` | 改用 `ops_runners.RUNNERS` |
| `backend/app/services/ops_scheduler.py` | `list_scheduler_jobs` 合并默认 cron |
| `backend/app/schemas/ops.py` / `frontend/...` | 可选 `cron_hours` 展示 |
| `backend/app/main.py` | lifespan 启停 embedded |
| `backend/tests/test_embedded_scheduler.py` | 新单测 |
| `backend/tests/test_bars_fill.py` | 改引用 embedded |
| `.env.example` / gap / smoke / OpsView 文案 | 文档与 UI |

---

### Task 1: settings + runners + 默认 cron 解析

**Files:**
- Create: `backend/app/services/ops_runners.py`
- Create: `backend/app/services/scheduler_defaults.py`
- Modify: `backend/app/core/settings.py`
- Modify: `backend/app/api/v1/ops.py`（改用 `RUNNERS`）
- Test: `backend/tests/test_scheduler_defaults.py`

**Interfaces:**
- Produces:
  - `ops_runners.RUNNERS: dict[str, Callable[..., dict]]`
  - `ops_runners.SCREEN_JOB_IDS = frozenset({"screen_intraday", "screen_post_close"})`
  - `ops_runners.needs_user_id(job_id: str) -> bool`
  - `scheduler_defaults.DEFAULT_CRON: dict[str, dict]`（见下方字面量）
  - `scheduler_defaults.resolve_cron(job_id, job_cfg) -> dict` 含 `hour`/`minute`/`day_of_week`/`hours`(list[int]|None)
  - Settings: `embedded_scheduler_enabled`, `scheduler_screen_user_id`；保留 `bars_scheduler_enabled`
  - `settings.scheduler_effective_enabled -> bool`（property：`embedded and bars`）

- [ ] **Step 1: 写失败单测（默认 cron）**

```python
# backend/tests/test_scheduler_defaults.py
from app.services.scheduler_defaults import resolve_cron
from app.services.ops_catalog import RUNNABLE_JOB_IDS


def test_defaults_cover_all_runnable() -> None:
    from app.services import scheduler_defaults as sd

    assert set(sd.DEFAULT_CRON) == set(RUNNABLE_JOB_IDS)


def test_resolve_calendar_monday() -> None:
    r = resolve_cron("sync_trade_calendar", {})
    assert r["hour"] == 7 and r["minute"] == 50 and r["day_of_week"] == "mon"
    assert r["hours"] is None


def test_resolve_intraday_hours() -> None:
    r = resolve_cron("screen_intraday", {})
    assert r["hours"] == [10, 14]
    assert r["minute"] == 2
    r2 = resolve_cron("screen_intraday", {"cron_hours": "9,11,13", "cron_minute_intraday": 5})
    assert r2["hours"] == [9, 11, 13] and r2["minute"] == 5


def test_config_overrides_hour() -> None:
    r = resolve_cron("purge_stale_cache", {"cron_hour": 20, "cron_minute": 1})
    assert r["hour"] == 20 and r["minute"] == 1
```

- [ ] **Step 2: 跑测确认失败**

```bash
cd backend && uv run pytest tests/test_scheduler_defaults.py -q
```

Expected: FAIL（模块不存在）

- [ ] **Step 3: 实现 `scheduler_defaults.py`**

字面量（与 spec 一致）：

```python
DEFAULT_CRON = {
    "sync_trade_calendar": {"hour": 7, "minute": 50, "day_of_week": "mon"},
    "sync_sector_flow_daily": {"hour": 17, "minute": 45, "day_of_week": "mon-fri"},
    "sync_limit_list": {"hour": 17, "minute": 50, "day_of_week": "mon-fri"},
    "screen_post_close": {"hour": 18, "minute": 0, "day_of_week": "mon-fri"},
    "fill_watchlist_bars": {"hour": 18, "minute": 0, "day_of_week": "mon-fri"},
    "batch_fill_stale": {"hour": 18, "minute": 30, "day_of_week": "mon-fri"},
    "purge_stale_cache": {"hour": 19, "minute": 15, "day_of_week": "mon-fri"},
    "screen_intraday": {
        "hours": [10, 14],
        "minute": 2,
        "day_of_week": "mon-fri",
    },
}
```

`resolve_cron(job_id, job_cfg)`：
- 未知 job_id → 返回 `{hour:8, minute:0, day_of_week:"mon-fri", hours:None}`
- `screen_intraday`：解析 `cron_hours`（逗号分隔 int）与 `cron_minute_intraday`；否则默认；`hour` 可取 `hours[0]` 仅供展示
- 其它：读 `cron_hour`/`cron_minute`/`cron_day_of_week`，缺省用 DEFAULT；钳制 hour 0–23、minute 0–59

- [ ] **Step 4: 实现 `ops_runners.py` 并改 `ops.py`**

```python
# ops_runners.py 核心
from app.services import (
    ops_auto_screen,
    ops_bars_fill,
    ops_purge,
    ops_sync_calendar,
    ops_sync_limit_list,
    ops_sync_sector,
)

SCREEN_JOB_IDS = frozenset({"screen_intraday", "screen_post_close"})

RUNNERS = {
    "purge_stale_cache": ops_purge.purge_stale_cache,
    "sync_trade_calendar": ops_sync_calendar.sync_trade_calendar,
    "sync_sector_flow_daily": ops_sync_sector.sync_sector_flow_daily,
    "sync_limit_list": ops_sync_limit_list.sync_limit_list,
    "fill_watchlist_bars": ops_bars_fill.fill_watchlist_bars,
    "batch_fill_stale": ops_bars_fill.batch_fill_stale,
    "screen_intraday": ops_auto_screen.screen_intraday,
    "screen_post_close": ops_auto_screen.screen_post_close,
}

def needs_user_id(job_id: str) -> bool:
    return job_id in SCREEN_JOB_IDS
```

`ops.py`：`from app.services.ops_runners import RUNNERS`；`_RUNNERS = RUNNERS` 或直接用 `RUNNERS`；断言 `set(RUNNERS) == RUNNABLE_JOB_IDS`（可放测试）。

- [ ] **Step 5: settings**

```python
embedded_scheduler_enabled: bool = True
scheduler_screen_user_id: str = ""
# 保留 bars_scheduler_enabled

@property
def scheduler_effective_enabled(self) -> bool:
    return bool(self.embedded_scheduler_enabled and self.bars_scheduler_enabled)
```

- [ ] **Step 6: 跑测**

```bash
cd backend && uv run pytest tests/test_scheduler_defaults.py tests/test_ops_catalog.py -q
```

Expected: PASS

- [ ] **Step 7: Commit** — 跳过（除非用户要求）

---

### Task 2: embedded_scheduler + lifespan

**Files:**
- Create: `backend/app/services/embedded_scheduler.py`
- Modify: `backend/app/main.py`
- Delete or thin: `backend/app/services/bars_scheduler.py`
- Create: `backend/tests/test_embedded_scheduler.py`
- Modify: `backend/tests/test_bars_fill.py`（scheduler 用例迁走或改 import）

**Interfaces:**
- Consumes: `RUNNERS`, `needs_user_id`, `resolve_cron`, `load_scheduler_config`, `settings.scheduler_effective_enabled`, `settings.scheduler_screen_user_id`
- Produces: `start_embedded_scheduler()` / `stop_embedded_scheduler()` / `_run_job(job_id: str) -> None`

- [ ] **Step 1: 写失败单测**

```python
# backend/tests/test_embedded_scheduler.py
from unittest.mock import MagicMock, patch
from app.services import embedded_scheduler as es
from app.services.ops_catalog import RUNNABLE_JOB_IDS


def test_runners_cover_runnable() -> None:
    from app.services.ops_runners import RUNNERS

    assert set(RUNNERS) == set(RUNNABLE_JOB_IDS)


def test_run_job_skips_when_master_disabled(monkeypatch) -> None:
    monkeypatch.setattr(
        es,
        "get_settings",
        lambda: type("S", (), {"scheduler_effective_enabled": False, "scheduler_screen_user_id": ""})(),
    )
    with patch.object(es, "SessionLocal") as sl:
        es._run_job("purge_stale_cache")
    sl.assert_not_called()


def test_run_job_skips_when_not_enabled(monkeypatch) -> None:
    monkeypatch.setattr(
        es,
        "get_settings",
        lambda: type("S", (), {"scheduler_effective_enabled": True, "scheduler_screen_user_id": "u1"})(),
    )
    db = MagicMock()
    monkeypatch.setattr(es, "SessionLocal", lambda: db)
    monkeypatch.setattr(
        es,
        "load_scheduler_config",
        lambda _db: {"config": {"purge_stale_cache": {"enabled": False}}},
    )
    with patch.dict(es.RUNNERS, {"purge_stale_cache": MagicMock()}, clear=False):
        es._run_job("purge_stale_cache")
        es.RUNNERS["purge_stale_cache"].assert_not_called()


def test_screen_skips_without_user(monkeypatch) -> None:
    monkeypatch.setattr(
        es,
        "get_settings",
        lambda: type("S", (), {"scheduler_effective_enabled": True, "scheduler_screen_user_id": ""})(),
    )
    db = MagicMock()
    monkeypatch.setattr(es, "SessionLocal", lambda: db)
    monkeypatch.setattr(
        es,
        "load_scheduler_config",
        lambda _db: {"config": {"screen_intraday": {"enabled": True}}},
    )
    runner = MagicMock()
    with patch.dict(es.RUNNERS, {"screen_intraday": runner}, clear=False):
        es._run_job("screen_intraday")
        runner.assert_not_called()


def test_screen_calls_with_user(monkeypatch) -> None:
    monkeypatch.setattr(
        es,
        "get_settings",
        lambda: type(
            "S",
            (),
            {"scheduler_effective_enabled": True, "scheduler_screen_user_id": "user-1"},
        )(),
    )
    db = MagicMock()
    monkeypatch.setattr(es, "SessionLocal", lambda: db)
    monkeypatch.setattr(
        es,
        "load_scheduler_config",
        lambda _db: {"config": {"screen_intraday": {"enabled": True}}},
    )
    runner = MagicMock(return_value={"success": True, "message": "ok"})
    with patch.dict(es.RUNNERS, {"screen_intraday": runner}, clear=False):
        es._run_job("screen_intraday")
        runner.assert_called_once_with(db, user_id="user-1")


def test_watchlist_skips_when_stale_running(monkeypatch) -> None:
    monkeypatch.setattr(
        es,
        "get_settings",
        lambda: type("S", (), {"scheduler_effective_enabled": True, "scheduler_screen_user_id": ""})(),
    )
    with es._running_guard:
        es._running.add("batch_fill_stale")
    try:
        with patch.object(es, "SessionLocal") as sl:
            es._run_job("fill_watchlist_bars")
        sl.assert_not_called()
    finally:
        with es._running_guard:
            es._running.discard("batch_fill_stale")
```

- [ ] **Step 2: 跑测确认失败**

```bash
cd backend && uv run pytest tests/test_embedded_scheduler.py -q
```

Expected: FAIL

- [ ] **Step 3: 实现 `embedded_scheduler.py`**

要点：
- `_locks: dict[str, threading.Lock]` 为每个 `RUNNABLE_JOB_IDS` 一把锁
- `_running: set[str]` + `_running_guard`
- `_run_job`：若非 `scheduler_effective_enabled` return；非阻塞锁；若 `fill_watchlist_bars` 且 `batch_fill_stale in _running` → 释放锁并 return；读 config enabled；选股无 user → warning + return；`runner(db)` 或 `runner(db, user_id=...)`；异常 `logger.exception`
- `start_embedded_scheduler`：若非 effective return；对每个 runnable `resolve_cron` → `CronTrigger`：
  - intraday：`CronTrigger(day_of_week=..., hour=",".join(map(str, hours)), minute=minute)`
  - 其它：`CronTrigger(day_of_week=..., hour=hour, minute=minute)`
- `stop_embedded_scheduler`：shutdown

- [ ] **Step 4: 改 `main.py`**

```python
from app.services.embedded_scheduler import start_embedded_scheduler, stop_embedded_scheduler
start_embedded_scheduler()
...
stop_embedded_scheduler()
```

删除 `bars_scheduler.py`（或留 re-export 指向 embedded，推荐删除并改 `test_bars_fill` 中旧测）。

- [ ] **Step 5: 跑测**

```bash
cd backend && uv run pytest tests/test_embedded_scheduler.py tests/test_bars_fill.py -q
```

Expected: PASS

- [ ] **Step 6: Commit** — 跳过

---

### Task 3: list_scheduler_jobs 合并默认 + Ops 文案

**Files:**
- Modify: `backend/app/services/ops_scheduler.py`（`list_scheduler_jobs`）
- Modify: `backend/app/schemas/ops.py`（可选 `cron_hours: str | None`）
- Modify: `frontend/src/api/ops.ts`、`frontend/src/views/OpsView.vue`
- Test: `backend/tests/test_ops_scheduler_defaults.py`（或并入现有）

**Interfaces:**
- Consumes: `resolve_cron` / `DEFAULT_CRON`
- Produces: list 行在 config 缺省时仍有 `cron_hour`/`cron_minute`/`cron_day_of_week`；`screen_intraday` 另有 `cron_hours` 字符串

- [ ] **Step 1: 单测**

```python
def test_list_merges_default_cron() -> None:
    from unittest.mock import MagicMock, patch
    from app.services import ops_scheduler

    db = MagicMock()
    with patch.object(ops_scheduler, "load_scheduler_config", return_value={"config": {}}), patch.object(
        ops_scheduler, "load_job_run_meta", return_value=None
    ):
        rows = {r["job_id"]: r for r in ops_scheduler.list_scheduler_jobs(db)}
    assert rows["purge_stale_cache"]["cron_hour"] == 19
    assert rows["purge_stale_cache"]["cron_minute"] == 15
    assert rows["screen_intraday"]["cron_hours"] == "10,14"
```

- [ ] **Step 2: 实现合并逻辑**

在 `list_scheduler_jobs` 循环内，对 `job_id in RUNNABLE_JOB_IDS`（或全部有 DEFAULT 的）：
```python
resolved = resolve_cron(spec.job_id, job_cfg)
cron_hour = job_cfg.get("cron_hour", resolved["hour"])
...
# screen_intraday:
cron_hours = job_cfg.get("cron_hours") or (
    ",".join(map(str, resolved["hours"])) if resolved.get("hours") else None
)
```

Schema / TS 增加可选 `cron_hours?: string | null`。

- [ ] **Step 3: OpsView**

- `scheduleText`：若 `j.job_id === 'screen_intraday' && j.cron_hours` → 返回 `` `${d} ${j.cron_hours}:${m}` ``（m 用 cron_minute）
- subtitle / 定时任务区 muted：说明「内嵌调度覆盖全部可跑 job；选股定时需 SCHEDULER_SCREEN_USER_ID」

- [ ] **Step 4: 跑测 + 前端 build**

```bash
cd backend && uv run pytest tests/test_ops_scheduler_defaults.py tests/test_embedded_scheduler.py -q
cd ../frontend && npm run build
```

Expected: PASS / build OK

- [ ] **Step 5: Commit** — 跳过

---

### Task 4: .env.example + gap/smoke + 全量验收

**Files:**
- Modify: `.env.example`
- Modify: `docs/gap-vs-desktop.md`
- Modify: `docs/smoke-checklist.md`

- [ ] **Step 1: `.env.example` 追加**

```bash
# 内嵌调度（覆盖全部可跑 job；与 BARS_SCHEDULER_ENABLED 同时为 true 才启动）
EMBEDDED_SCHEDULER_ENABLED=true
# 兼容旧开关；任一为 false 则关闭内嵌调度
BARS_SCHEDULER_ENABLED=true
# 盘中/盘后选股定时写入该用户的 screener_runs；空则跳过选股定时
SCHEDULER_SCREEN_USER_ID=
```

- [ ] **Step 2: gap** — 「内嵌 APScheduler」改为覆盖全部可跑 job；下一刀去掉该项

- [ ] **Step 3: smoke** — Ops 可开关非日 K 可跑 job；选股定时需 env user

- [ ] **Step 4: 全量**

```bash
cd backend && uv run pytest -q
cd ../frontend && npm run build
```

Expected: 全绿

- [ ] **Step 5: Commit** — 跳过

---

## Spec coverage（自审）

| Spec 项 | Task |
|---------|------|
| 全部 RUNNABLE 调度 | T2 |
| SCHEDULER_SCREEN_USER_ID | T2 |
| 默认 cron / config 覆盖 | T1+T2 |
| embedded ∧ bars 总开关 | T1+T2 |
| runners 同源 | T1 |
| 日 K 互斥 | T2 |
| Ops 只读 cron + 文案 | T3 |
| .env / gap / smoke | T4 |
| 测试 + build | T2–T4 |

无 TBD；接口名前后一致。

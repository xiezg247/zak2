# 全市场日 K 首下 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development（推荐）或 executing-plans。步骤用 `- [ ]` 跟踪。

**Goal:** Ops 可跑 `batch_download_universe`：按 `app.universe` 对缺 overview / 起点过晚的标的，从统一起点下载日 K。

**Architecture:** 在 `bar_download` 增加起点解析与目标筛选；在 `ops_bars_fill` 实现 job 并注册 RUNNABLE；扩展三者互斥；Ops 增加快捷按钮。

**Tech Stack:** FastAPI ops runners、现有 `download_daily_bars`、Vue OpsView、pytest。

**Spec:** `docs/superpowers/specs/2026-08-07-batch-download-universe-design.md`

## Global Constraints

- 只改 zak2；不改 zak / vnpy-*
- 不实现 `sync_universe`；不做起点 UI；无多线程 / no-data 永久跳过
- Commit 仅用户明确要求时（默认跳过）

---

## File map

| 文件 | 职责 |
|------|------|
| `backend/app/services/bar_download.py` | `parse_universe_start`、`list_universe_symbols`、`select_universe_daily_targets` |
| `backend/app/services/ops_bars_fill.py` | `batch_download_universe` |
| `backend/app/services/ops_catalog.py` | `RUNNABLE` 加入该 job |
| `backend/app/services/ops_runners.py` | runner 映射 |
| `backend/app/services/scheduler_defaults.py` | 默认 cron 16:20 |
| `backend/app/services/embedded_scheduler.py` | 三者互斥 |
| `backend/tests/test_bars_fill.py` | 筛选 / job 单测 |
| `backend/tests/test_embedded_scheduler.py` | 互斥 |
| `backend/tests/test_ops_catalog.py` | runnable 断言 |
| `frontend/src/views/OpsView.vue` | 按钮 + 文案 |
| `.env.example` | `BARS_UNIVERSE_START` 注释 |
| `docs/gap-vs-desktop.md` / `smoke-checklist.md` | 文档 |

---

### Task 1: bar_download — 起点与目标筛选

**Files:**
- Modify: `backend/app/services/bar_download.py`
- Modify: `backend/tests/test_bars_fill.py`

**Interfaces:**
- `DEFAULT_UNIVERSE_START = date(2020, 1, 1)`
- `parse_universe_start(raw: str | None = None) -> date`  
  - 读 env `BARS_UNIVERSE_START`（若 raw 为 None）；非法/`YYYY-MM-DD` 解析失败 → 默认
- `list_universe_symbols(db) -> list[tuple[str, str]]` — `(symbol, exchange)`，`ORDER BY exchange, symbol`；exchange 经 `normalize_exchange`
- `select_universe_daily_targets(universe: list[tuple[str, str]], overview_starts: dict[tuple[str, str], date | None], *, unified_start: date) -> list[tuple[str, str]]`  
  - 无 overview key → 纳入  
  - overview start 为 None 或 `start > unified_start` → 纳入  
  - 否则跳过  
  - 保序

SQL for list:

```sql
SELECT symbol, exchange
FROM app.universe
WHERE symbol IS NOT NULL AND exchange IS NOT NULL
ORDER BY exchange, symbol
```

- [ ] **Step 1: 写失败单测**

```python
from datetime import date
from app.services import bar_download as bars


def test_parse_universe_start_default(monkeypatch) -> None:
    monkeypatch.delenv("BARS_UNIVERSE_START", raising=False)
    assert bars.parse_universe_start(None) == date(2020, 1, 1)


def test_parse_universe_start_env(monkeypatch) -> None:
    monkeypatch.setenv("BARS_UNIVERSE_START", "2018-06-01")
    assert bars.parse_universe_start(None) == date(2018, 6, 1)


def test_parse_universe_start_invalid(monkeypatch) -> None:
    monkeypatch.setenv("BARS_UNIVERSE_START", "bad")
    assert bars.parse_universe_start(None) == date(2020, 1, 1)


def test_select_universe_daily_targets() -> None:
    uni = [("600519", "SSE"), ("000001", "SZSE"), ("300750", "SZSE")]
    starts = {
        ("600519", "SSE"): date(2020, 1, 1),  # covered
        ("000001", "SZSE"): date(2021, 1, 1),  # start too late
        # 300750 missing
    }
    out = bars.select_universe_daily_targets(
        uni, starts, unified_start=date(2020, 1, 1)
    )
    assert out == [("000001", "SZSE"), ("300750", "SZSE")]
```

- [ ] **Step 2: RED** — `cd backend && python -m pytest tests/test_bars_fill.py::test_select_universe_daily_targets -v`  
  Expected: FAIL（函数未定义）

- [ ] **Step 3: 实现** `parse_universe_start` / `list_universe_symbols` / `select_universe_daily_targets`（见 Interfaces）

`list_universe_symbols` 可用 MagicMock 另写一测或与 Task 2 一起测；本 Task 至少覆盖 parse + select。

- [ ] **Step 4: GREEN** — `pytest tests/test_bars_fill.py -k "parse_universe or select_universe" -v` PASS

- [ ] **Step 5: Commit** — 跳过

---

### Task 2: batch_download_universe job + 注册

**Files:**
- Modify: `backend/app/services/ops_bars_fill.py`
- Modify: `backend/app/services/ops_catalog.py`
- Modify: `backend/app/services/ops_runners.py`
- Modify: `backend/app/services/scheduler_defaults.py`
- Modify: `backend/tests/test_bars_fill.py`
- Modify: `backend/tests/test_ops_catalog.py`

**Interfaces:**
- `JOB_UNIVERSE = "batch_download_universe"`
- `batch_download_universe(db) -> dict`  
  - 空 universe → `success=False`，`message` 含「同步 A 股列表」或「universe」  
  - 无 token → 同 fill  
  - 加载全部 overview start（interval=d）→ select → `[:_max_symbols()]`  
  - 每标的：`download_daily_bars(db, symbol, exchange, start=unified_start, end=as_of)`；commit/rollback 同 `_fill_one` 风格  
  - `up_to_date` / `skipped_covered` = 池内未纳入数（universe 总数 − targets 未截断前）；`attempted` = 实际下载循环数  
  - `save_job_run_meta`

加载 overview starts 建议：

```sql
SELECT symbol, exchange, start
FROM public.dbbaroverview
WHERE interval = 'd'
```

映射 key `(symbol, normalize_exchange(exchange))` → `overview_end_date(start)`（复用日期解析）。

- [ ] **Step 1: 写失败单测**

```python
def test_batch_download_universe_empty(monkeypatch) -> None:
    monkeypatch.setenv("BARS_FILL_SLEEP_SEC", "0")
    db = MagicMock()
    with (
        patch.object(ops_bars_fill.ts, "require_token"),
        patch.object(ops_bars_fill.bars, "list_universe_symbols", return_value=[]),
        patch.object(ops_bars_fill, "save_job_run_meta"),
    ):
        out = ops_bars_fill.batch_download_universe(db)
    assert out["success"] is False
    assert "列表" in out["message"] or "universe" in out["message"].lower()


def test_batch_download_universe_respects_max(monkeypatch) -> None:
    monkeypatch.setenv("BARS_FILL_MAX_SYMBOLS", "1")
    monkeypatch.setenv("BARS_FILL_SLEEP_SEC", "0")
    monkeypatch.setenv("BARS_UNIVERSE_START", "2020-01-01")
    db = MagicMock()
    with (
        patch.object(ops_bars_fill.ts, "require_token"),
        patch.object(ops_bars_fill.bars, "as_of_trade_date", return_value=date(2024, 8, 5)),
        patch.object(
            ops_bars_fill.bars,
            "list_universe_symbols",
            return_value=[("600519", "SSE"), ("000001", "SZSE")],
        ),
        patch.object(ops_bars_fill.bars, "parse_universe_start", return_value=date(2020, 1, 1)),
        patch.object(
            ops_bars_fill,
            "_load_overview_starts",
            return_value={},
        ),
        patch.object(ops_bars_fill.bars, "download_daily_bars", return_value=2) as dl,
        patch.object(ops_bars_fill, "save_job_run_meta"),
    ):
        # commit path: patch db.commit
        out = ops_bars_fill.batch_download_universe(db)
    assert out["attempted"] == 1
    assert out["bars_added"] == 2
    assert dl.call_count == 1
```

（若实现不用 `_load_overview_starts` 私有函数，改为 patch `db.execute` 返回空 overview 亦可；以最终实现为准，但断言 max=1 必须成立。）

- [ ] **Step 2: RED**

- [ ] **Step 3: 实现 job**

伪代码：

```python
def batch_download_universe(db: Session) -> dict[str, Any]:
    try:
        ts.require_token()
    except ts.TushareNotConfiguredError as exc:
        ...  # same as _run_pool no-token

    universe = bars.list_universe_symbols(db)
    if not universe:
        out = {"success": False, "message": "全 A 股列表为空，请先同步 A 股列表", ...zeros}
        save_job_run_meta(...)
        return out

    unified = bars.parse_universe_start(None)
    as_of = bars.as_of_trade_date(db)
    starts = _load_overview_starts(db)
    targets = bars.select_universe_daily_targets(universe, starts, unified_start=unified)
    skipped_covered = len(universe) - len(targets)
    pool = targets[: _max_symbols()]
    # loop download_daily_bars(unified, as_of); sleep; aggregate like _run_pool
```

- [ ] **Step 4: 注册**

`ops_catalog.RUNNABLE_JOB_IDS` 加 `"batch_download_universe"`。  
`ops_runners.RUNNERS["batch_download_universe"] = ops_bars_fill.batch_download_universe`。  
`scheduler_defaults.DEFAULT_CRON["batch_download_universe"] = {"hour": 16, "minute": 20, "day_of_week": "mon-fri"}`。  
`test_ops_catalog.py` 断言该 id ∈ RUNNABLE。

可选：更新 catalog description 为「全 A 日 K 首下/补起点（Web 可跑，单次上限）」。

- [ ] **Step 5: GREEN** —  
`pytest tests/test_bars_fill.py tests/test_ops_catalog.py tests/test_scheduler_defaults.py -q` PASS

- [ ] **Step 6: Commit** — 跳过

---

### Task 3: 互斥 + Ops UI + env

**Files:**
- Modify: `backend/app/services/embedded_scheduler.py`
- Modify: `backend/tests/test_embedded_scheduler.py`
- Modify: `frontend/src/views/OpsView.vue`
- Modify: `.env.example`

**Interfaces:**
- `_BARS_JOBS = frozenset({"fill_watchlist_bars", "batch_fill_stale", "batch_download_universe"})`
- 在 `_run_job` 进 `_running` 前：若 `job_id in _BARS_JOBS` 且 `_running ∩ _BARS_JOBS` 非空（不含自己），则 release lock 并 return

- [ ] **Step 1: 互斥单测**

```python
def test_universe_skips_when_stale_running(monkeypatch) -> None:
    monkeypatch.setattr(
        es,
        "get_settings",
        lambda: type("S", (), {"scheduler_effective_enabled": True, "scheduler_screen_user_id": ""})(),
    )
    with es._running_guard:
        es._running.add("batch_fill_stale")
    try:
        with patch.object(es, "SessionLocal") as sl:
            es._run_job("batch_download_universe")
        sl.assert_not_called()
    finally:
        with es._running_guard:
            es._running.discard("batch_fill_stale")
```

扩展现有 `test_watchlist_skips_when_stale_running` 逻辑，确保 universe 运行时 watchlist 也跳过（可再加一条）。

替换旧硬编码：

```python
# before adding to _running:
if job_id in _BARS_JOBS and (_running & _BARS_JOBS):
    lock.release()
    _logger.info("embedded scheduler skip %s: another bars job running", job_id)
    return
```

删除仅 `fill_watchlist_bars` vs `batch_fill_stale` 的旧特例（由集合互斥覆盖）。

- [ ] **Step 2: RED → 实现 → GREEN**  
`pytest tests/test_embedded_scheduler.py -q`

- [ ] **Step 3: OpsView**

文案：

```text
· Web 可补全自选 / 过期日 K / 全市场首下（需 app.universe + TUSHARE_TOKEN；起点见 BARS_UNIVERSE_START）
```

按钮（在过期按钮旁）：

```vue
<button
  type="button"
  class="ghost"
  :disabled="!!busy"
  @click="runJob('batch_download_universe', true)"
>
  {{ busy === 'batch_download_universe' ? '提交中…' : '全市场日 K 首下' }}
</button>
```

`runJob` 分支：把 `batch_download_universe` 与 fill 一样走 `opsApi.runJob`：

```typescript
} else if (
  jobId === 'fill_watchlist_bars' ||
  jobId === 'batch_fill_stale' ||
  jobId === 'batch_download_universe'
) {
```

- [ ] **Step 4: `.env.example`**

```bash
# 全市场日 K 首下统一起点（YYYY-MM-DD；默认 2020-01-01）
# BARS_UNIVERSE_START=2020-01-01
# 单次最多标的数 / 限流（与补全共用）
# BARS_FILL_MAX_SYMBOLS=500
# BARS_FILL_SLEEP_SEC=0.05
```

- [ ] **Step 5: build** — `cd frontend && npm run build` 成功

- [ ] **Step 6: Commit** — 跳过

---

### Task 4: 文档 + 全量验收

**Files:**
- Modify: `docs/gap-vs-desktop.md`
- Modify: `docs/smoke-checklist.md`

- [ ] **Step 1: gap** — 「日 K Web 补全」备注改为含全市场首下（薄：单次上限、依赖已有 `app.universe`）。建议下一刀去掉「无全市场首下」措辞。

- [ ] **Step 2: smoke** — Ops 条目追加：可提交**全市场日 K 首下**；无 universe / 无 token 有明确失败文案。

- [ ] **Step 3: 全量**

```bash
cd backend && python -m pytest -q
cd frontend && npm run build
```

Expected: 全绿 + build 成功。

- [ ] **Step 4: Commit** — 跳过

---

## Spec coverage（自检）

| Spec 项 | Task |
|---------|------|
| 筛选 / 起点 env | 1 |
| job + RUNNABLE + cron 16:20 | 2 |
| 互斥三者 | 3 |
| Ops 按钮文案 | 3 |
| gap / smoke / pytest+build | 4 |
| 非目标 sync_universe 等 | 未实现（符合） |

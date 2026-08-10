# Web 同步 A 股列表（sync_universe）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development（推荐）或 executing-plans。步骤用 `- [ ]` 跟踪。

**Goal:** Ops 可跑 `sync_universe`：Tushare `stock_basic` 全量替换 `app.universe`。

**Architecture:** 纯函数映射 + `ops_sync_universe` job（DELETE+分批 INSERT + meta）→ 注册 RUNNABLE/cron → Ops 快捷按钮。

**Tech Stack:** FastAPI ops runners、现有 `tushare_client`、Vue OpsView、pytest。

**Spec:** `docs/superpowers/specs/2026-08-07-sync-universe-design.md`

## Global Constraints

- 只改 zak2；不改 zak；不接 TickFlow
- Commit 仅用户明确要求时（默认跳过）

---

## File map

| 文件 | 职责 |
|------|------|
| `backend/app/services/ops_sync_universe.py` | 映射 + sync job |
| `backend/tests/test_ops_sync_universe.py` | 单测 |
| `backend/app/services/ops_catalog.py` | RUNNABLE + 描述 |
| `backend/app/services/ops_runners.py` | runner |
| `backend/app/services/scheduler_defaults.py` | 周一 08:00 |
| `frontend/src/views/OpsView.vue` | 按钮 + 文案 |
| `docs/gap-vs-desktop.md` / `smoke-checklist.md` | 文档 |

---

### Task 1: 映射纯函数 + sync job 核心

**Files:**
- Create: `backend/app/services/ops_sync_universe.py`
- Create: `backend/tests/test_ops_sync_universe.py`

**Interfaces:**
- `JOB_ID = "sync_universe"`
- `UNIVERSE_SYNCED_AT_KEY = "universe_synced_at"`
- `INSERT_CHUNK = 500`
- `parse_ts_code(ts_code: str) -> tuple[str, str] | None`  
  - `"600519.SH"` → `("600519", "SSE")`；`.SZ`→`SZSE`；`.BJ`→`BSE`；非法/未知 → `None`
- `rows_from_stock_basic(raw: list[dict]) -> tuple[list[dict], int]`  
  - 每项 `{"symbol","exchange","name"}`；返回 `(rows, skipped)`；同 `(symbol,exchange)` 去重保序
- `sync_universe(db) -> dict`  
  - 无 token → fail  
  - `ts.query("stock_basic", {"list_status": "L"}, fields="ts_code,name")`  
  - 映射后 0 条 → fail「无有效标的」  
  - 事务：DELETE → 分批 INSERT → upsert `app.meta`  
  - 成功：`{success:True, message:..., count:N, skipped:K}`

meta upsert（与 recipe_weights 类似）：

```sql
INSERT INTO app.meta (key, value) VALUES (:k, :v)
ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
```

（若表无 UNIQUE 冲突键，改为 DELETE+INSERT 同 key；实现时先看库内其它 meta 写法。）

- [ ] **Step 1: 写失败单测**

```python
from app.services.ops_sync_universe import parse_ts_code, rows_from_stock_basic


def test_parse_ts_code() -> None:
    assert parse_ts_code("600519.SH") == ("600519", "SSE")
    assert parse_ts_code("000001.SZ") == ("000001", "SZSE")
    assert parse_ts_code("830799.BJ") == ("830799", "BSE")
    assert parse_ts_code("600519.XX") is None
    assert parse_ts_code("") is None


def test_rows_from_stock_basic_skips_unknown() -> None:
    rows, skipped = rows_from_stock_basic(
        [
            {"ts_code": "600519.SH", "name": "茅台"},
            {"ts_code": "BAD", "name": "x"},
            {"ts_code": "000001.SZ", "name": "平安"},
        ]
    )
    assert skipped == 1
    assert rows == [
        {"symbol": "600519", "exchange": "SSE", "name": "茅台"},
        {"symbol": "000001", "exchange": "SZSE", "name": "平安"},
    ]
```

```python
from unittest.mock import MagicMock, patch
from app.services import ops_sync_universe as svc


def test_sync_universe_no_token() -> None:
    db = MagicMock()
    with (
        patch.object(svc.ts, "require_token", side_effect=svc.ts.TushareNotConfiguredError("未配置")),
        patch.object(svc, "save_job_run_meta"),
    ):
        out = svc.sync_universe(db)
    assert out["success"] is False
    assert "未配置" in out["message"]


def test_sync_universe_replace(monkeypatch) -> None:
    db = MagicMock()
    raw = [{"ts_code": "600519.SH", "name": "茅台"}]
    with (
        patch.object(svc.ts, "require_token"),
        patch.object(svc.ts, "query", return_value=raw) as q,
        patch.object(svc, "save_job_run_meta"),
    ):
        out = svc.sync_universe(db)
    q.assert_called_once()
    assert out["success"] is True
    assert out["count"] == 1
    assert out["skipped"] == 0
    # DELETE then INSERT executed
    assert db.execute.call_count >= 2
    db.commit.assert_called()
```

- [ ] **Step 2: RED** — `cd backend && python -m pytest tests/test_ops_sync_universe.py -v`  
  Expected: 模块不存在

- [ ] **Step 3: 实现 `ops_sync_universe.py`**

参考结构：

```python
_SUFFIX = {"SH": "SSE", "SZ": "SZSE", "BJ": "BSE"}

def parse_ts_code(ts_code: str) -> tuple[str, str] | None:
    text = (ts_code or "").strip().upper()
    if "." not in text:
        return None
    code, suf = text.rsplit(".", 1)
    exch = _SUFFIX.get(suf)
    if not code or not exch:
        return None
    return code, exch

def sync_universe(db: Session) -> dict[str, Any]:
    ...
```

捕获 `HTTPException` / 网络错误 → `success=False`，rollback。

- [ ] **Step 4: GREEN** — 同上 pytest PASS

- [ ] **Step 5: Commit** — 跳过

---

### Task 2: 注册 RUNNABLE + defaults + catalog 文案

**Files:**
- Modify: `backend/app/services/ops_catalog.py`
- Modify: `backend/app/services/ops_runners.py`
- Modify: `backend/app/services/scheduler_defaults.py`
- Modify: `backend/tests/test_ops_catalog.py`（若需显式断言）

**Interfaces:**
- `RUNNABLE_JOB_IDS` 增加 `"sync_universe"`
- `RUNNERS["sync_universe"] = ops_sync_universe.sync_universe`
- `DEFAULT_CRON["sync_universe"] = {"hour": 8, "minute": 0, "day_of_week": "mon"}`
- JobSpec description → `"Tushare stock_basic → app.universe（Web 可跑）"`

- [ ] **Step 1: 改注册三处**

- [ ] **Step 2: 断言**

`test_ops_catalog.py` 增加：`assert "sync_universe" in RUNNABLE_JOB_IDS`

- [ ] **Step 3: GREEN**

```bash
cd backend && python -m pytest tests/test_ops_sync_universe.py tests/test_ops_catalog.py tests/test_scheduler_defaults.py -q
```

- [ ] **Step 4: Commit** — 跳过

---

### Task 3: Ops UI

**Files:**
- Modify: `frontend/src/views/OpsView.vue`

- [ ] **Step 1: 文案**

日 K 区说明改为含：可先「同步 A 股列表」，再首下；需 `TUSHARE_TOKEN`。

示例：

```text
· Web 可同步 A 股列表 / 补全自选 / 过期 / 全市场首下（需 TUSHARE_TOKEN；首下另需 app.universe；起点 BARS_UNIVERSE_START）
```

- [ ] **Step 2: 按钮**（放在日 K 按钮组最前）：

```vue
<button
  type="button"
  class="ghost"
  :disabled="!!busy"
  @click="runJob('sync_universe', true)"
>
  {{ busy === 'sync_universe' ? '提交中…' : '同步 A 股列表' }}
</button>
```

- [ ] **Step 3: runJob 分支**

把 `sync_universe` 加入与 bars 相同的 `opsApi.runJob` 列表：

```typescript
} else if (
  jobId === 'sync_universe' ||
  jobId === 'fill_watchlist_bars' ||
  jobId === 'batch_fill_stale' ||
  jobId === 'batch_download_universe'
) {
```

- [ ] **Step 4: build** — `cd frontend && npm run build` 成功

- [ ] **Step 5: Commit** — 跳过

---

### Task 4: 文档 + 全量验收

**Files:**
- Modify: `docs/gap-vs-desktop.md`
- Modify: `docs/smoke-checklist.md`

- [ ] **Step 1: gap**  
  - 运维/可跑：注明 Web 可 `sync_universe`（Tushare，非 TickFlow）  
  - 日 K 备注：列表可由 Web sync，不再「仅桌面」

- [ ] **Step 2: smoke** — Ops 可提交**同步 A 股列表**；无 token / 空结果有明确失败

- [ ] **Step 3: 全量**

```bash
cd backend && python -m pytest -q
cd frontend && npm run build
```

- [ ] **Step 4: Commit** — 跳过

---

## Spec coverage（自检）

| Spec 项 | Task |
|---------|------|
| 映射 / 全量替换 / meta | 1 |
| RUNNABLE + cron 周一 08:00 | 2 |
| Ops 按钮文案 | 3 |
| gap / smoke / 验收 | 4 |
| 非目标 TickFlow | 未实现（符合） |

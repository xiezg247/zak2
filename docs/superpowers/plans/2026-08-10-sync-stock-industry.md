# Web 同步行业映射（sync_stock_industry）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development（推荐）或 executing-plans。步骤用 `- [ ]` 跟踪。

**Goal:** Ops 可跑 `sync_stock_industry`：Tushare 申万 L2（失败回退 stock_basic）全量替换 `app.stock_industry`。

**Architecture:** 仿 `sync_universe`：DDL + 纯函数映射 + job DELETE/chunk INSERT + meta → RUNNABLE/cron → Ops 快捷按钮。本刀不改选股/行情读路径。

**Tech Stack:** FastAPI ops、`tushare_client`、Vue OpsView、pytest。

**Spec:** `docs/superpowers/specs/2026-08-10-sync-stock-industry-design.md`

## Global Constraints

- 只改 zak2；不改 zak / vnpy-*
- 不写 `tushare_factor_cache`；不接硬过滤/quotes/engine 读表
- Commit 仅用户明确要求时（默认跳过）
- 不打真网

**Clarifications:**

- 复用 `ops_sync_universe.parse_ts_code`（勿复制后缀映射）
- 申万活跃判定：`out_date` 为空字符串视为活跃（与桌面 `_is_active_member` 一致）
- `industry`：优先 `l2_name`，空则用 `l1_name`

---

## File map

| 文件 | 职责 |
|------|------|
| `backend/app/services/ops_sync_stock_industry.py` | **新建** DDL + 映射 + sync |
| `backend/tests/test_ops_sync_stock_industry.py` | **新建** 单测 |
| `backend/app/services/ops_catalog.py` | RUNNABLE + 描述 |
| `backend/app/services/ops_runners.py` | 注册 runner |
| `backend/app/services/scheduler_defaults.py` | 周一 08:15 |
| `backend/tests/test_ops_catalog.py` / `test_scheduler_defaults.py` | 断言含新 job |
| `frontend/src/views/OpsView.vue` | 按钮 + 文案 + runJob 分支 |
| `docs/gap-vs-desktop.md` / `smoke-checklist.md` | 文档 |

---

### Task 1: 服务 + 单测

**Files:**
- Create: `backend/app/services/ops_sync_stock_industry.py`
- Create: `backend/tests/test_ops_sync_stock_industry.py`

**Interfaces:**
- `JOB_ID = "sync_stock_industry"`
- `SYNCED_AT_KEY = "stock_industry_synced_at"`
- `INSERT_CHUNK = 500`
- `DDL`：`CREATE TABLE IF NOT EXISTS app.stock_industry (...)` 按 spec
- `ensure_table(db)` — execute DDL（可不 commit，由 sync 统一 commit；或与 limit_list 一致）
- `rows_from_sw_members(raw: list[dict]) -> tuple[list[dict], int]`  
  - 输出项：`symbol, exchange, industry, industry_l1, source="sw2021_l2"`  
  - 跳过：无 ts 映射、无行业名、有 out_date  
  - `(symbol,exchange)` 去重保序  
- `rows_from_stock_basic_industry(raw) -> tuple[list[dict], int]`  
  - `source="stock_basic"`，`industry_l1=""`  
- `sync_stock_industry(db) -> dict`  
  - 无 token → fail  
  - `ensure_table`  
  - `ts.query("index_member_all", {"is_new": "Y"}, fields="ts_code,l1_name,l2_name,out_date")`  
  - 若 sw rows 空：`ts.query("stock_basic", {"list_status": "L"}, fields="ts_code,industry")`  
  - 仍空 → fail「无有效行业映射」  
  - DELETE + chunk INSERT + meta upsert + commit  
  - 返回含 `source`

INSERT 列：`symbol, exchange, industry, industry_l1, source, updated_at`

- [ ] **Step 1: 写失败单测**

```python
# backend/tests/test_ops_sync_stock_industry.py
from __future__ import annotations

from unittest.mock import MagicMock, call, patch

from app.services import ops_sync_stock_industry as svc


def test_rows_from_sw_members() -> None:
    rows, skipped = svc.rows_from_sw_members(
        [
            {"ts_code": "600519.SH", "l1_name": "可选消费", "l2_name": "白酒", "out_date": ""},
            {"ts_code": "000001.SZ", "l1_name": "金融", "l2_name": "银行", "out_date": "20200101"},
            {"ts_code": "BAD", "l2_name": "x", "out_date": ""},
            {"ts_code": "830799.BJ", "l1_name": "综合", "l2_name": "", "out_date": ""},
        ]
    )
    assert skipped >= 2  # out_date + BAD
    assert rows[0]["symbol"] == "600519"
    assert rows[0]["industry"] == "白酒"
    assert rows[0]["industry_l1"] == "可选消费"
    assert rows[0]["source"] == "sw2021_l2"
    # BJ 无 l2 时用 l1
    assert any(r["symbol"] == "830799" and r["industry"] == "综合" for r in rows)


def test_rows_from_stock_basic_industry() -> None:
    rows, skipped = svc.rows_from_stock_basic_industry(
        [{"ts_code": "600519.SH", "industry": "白酒"}, {"ts_code": "XX", "industry": "y"}]
    )
    assert skipped == 1
    assert rows == [
        {
            "symbol": "600519",
            "exchange": "SSE",
            "industry": "白酒",
            "industry_l1": "",
            "source": "stock_basic",
        }
    ]


def test_sync_sw_success() -> None:
    db = MagicMock()
    sw = [{"ts_code": "600519.SH", "l1_name": "消费", "l2_name": "白酒", "out_date": ""}]
    with (
        patch.object(svc.ts, "require_token"),
        patch.object(svc.ts, "query", return_value=sw) as q,
        patch.object(svc, "save_job_run_meta"),
        patch.object(svc, "ensure_table"),
    ):
        out = svc.sync_stock_industry(db)
    assert out["success"] is True
    assert out["count"] == 1
    assert out["source"] == "sw2021_l2"
    q.assert_called_once()
    assert db.execute.call_count >= 2
    db.commit.assert_called()


def test_sync_fallback_stock_basic() -> None:
    db = MagicMock()
    basic = [{"ts_code": "600519.SH", "industry": "白酒"}]

    def _query(api_name, params=None, *, fields=""):
        if api_name == "index_member_all":
            return []
        return basic

    with (
        patch.object(svc.ts, "require_token"),
        patch.object(svc.ts, "query", side_effect=_query),
        patch.object(svc, "save_job_run_meta"),
        patch.object(svc, "ensure_table"),
    ):
        out = svc.sync_stock_industry(db)
    assert out["success"] is True
    assert out["source"] == "stock_basic"
    assert out["count"] == 1


def test_sync_no_token() -> None:
    db = MagicMock()
    with (
        patch.object(svc.ts, "require_token", side_effect=svc.ts.TushareNotConfiguredError("未配置")),
        patch.object(svc, "save_job_run_meta"),
    ):
        out = svc.sync_stock_industry(db)
    assert out["success"] is False
    assert "未配置" in out["message"]


def test_sync_empty_fail() -> None:
    db = MagicMock()
    with (
        patch.object(svc.ts, "require_token"),
        patch.object(svc.ts, "query", return_value=[]),
        patch.object(svc, "save_job_run_meta"),
        patch.object(svc, "ensure_table"),
    ):
        out = svc.sync_stock_industry(db)
    assert out["success"] is False
    assert "无有效" in out["message"]
```

- [ ] **Step 2: RED → 实现 → GREEN**

```bash
cd /Users/xiezhigang/Projects/me/zak2/backend && uv run pytest tests/test_ops_sync_stock_industry.py -q
```

实现骨架对齐 `ops_sync_universe.py`（`_fail` / try-except / chunk INSERT / meta ON CONFLICT）。

- [ ] **Step 3: Commit** — 跳过

---

### Task 2: 注册 + Ops UI

**Files:**
- Modify: `ops_catalog.py` — `RUNNABLE` 加 `sync_stock_industry`；更新 `JobSpec` description
- Modify: `ops_runners.py` — import + `RUNNERS[...]`
- Modify: `scheduler_defaults.py` — `"sync_stock_industry": {"hour": 8, "minute": 15, "day_of_week": "mon"}`
- Modify: `tests/test_ops_catalog.py` — assert in RUNNABLE
- Modify: `tests/test_scheduler_defaults.py` — 若有「覆盖全部 runnable」测，应自动覆盖；必要时显式 assert 08:15
- Modify: `frontend/src/views/OpsView.vue`

**OpsView：**
1. `runJob` 异步分支列表加入 `'sync_stock_industry'`（与 sync_universe 同组）
2. 日 K actions 区「同步 A 股列表」旁加按钮「同步行业映射」
3. 文案补：可同步行业映射 → `app.stock_industry`

- [ ] **Step 1: 后端注册 + catalog/defaults 测绿**

```bash
cd /Users/xiezhigang/Projects/me/zak2/backend && uv run pytest tests/test_ops_catalog.py tests/test_scheduler_defaults.py tests/test_ops_sync_stock_industry.py -q
```

- [ ] **Step 2: OpsView + build**

```bash
cd /Users/xiezhigang/Projects/me/zak2/frontend && npm run build
```

- [ ] **Step 3: Commit** — 跳过

---

### Task 3: gap / smoke + 全量验收

**Files:**
- Modify: `docs/gap-vs-desktop.md`
- Modify: `docs/smoke-checklist.md`

- [ ] **Step 1: gap** — 运维备注 Web 可跑 `sync_stock_industry`；「建议下一刀」改为另定（非绑定）

- [ ] **Step 2: smoke** — Ops 可提交同步行业映射；无 token / 空结果失败文案；任务表可见开关

- [ ] **Step 3: 全量 pytest**

```bash
cd /Users/xiezhigang/Projects/me/zak2/backend && uv run pytest -q
```

Expected: 全绿（基线约 296+）

- [ ] **Step 4: Commit** — 跳过

---

## Spec coverage

| Spec | Task |
|------|------|
| 表 DDL + sw/basic 映射 + DELETE/INSERT | 1 |
| meta / save_job_run_meta / source | 1 |
| RUNNABLE / runner / cron 08:15 | 2 |
| Ops 按钮 + 文案 | 2 |
| gap / smoke | 3 |
| pytest + build | 2–3 |

## Placeholder scan

无 TBD。

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-08-10-sync-stock-industry.md`.

**Two execution options:**

1. **Subagent-Driven（推荐）**  
2. **Inline Execution**  

Which approach?

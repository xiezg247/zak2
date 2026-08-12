# Ops planned 第三批（策略预热 / 展望 skipped 壳）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 `warm_watchlist_strategy_cache`、`scan_horizon_outlook` 升级为可跑 job（诚实 skipped 壳；默认定时关）。

**Architecture:** 每 job 一薄服务模块（恒 skipped + `save_job_run_meta`）+ 单测；最后统一注册 RUNNABLE / RUNNERS / DEFAULT_CRON 并更新文档。不写 cache、不移植策略/展望管线。

**Tech Stack:** SQLAlchemy Session、pytest mock

**Spec:** `docs/superpowers/specs/2026-08-12-ops-planned-batch3-design.md`

## Global Constraints

- 只改 zak2；不改 zak / vnpy-*；不实现 `prefetch_concept_board` / `fill_focus_pool_minute`
- 不写 `watchlist_*_cache` / `radar_horizon_cache` / `radar_predict_cache`
- 恒 `skipped=True` + `success=False` + `save_job_run_meta(..., last_success=False)`
- enabled 默认 false；仅加 DEFAULT_CRON
- commit message 简体中文：`<type>(<scope>): <简述>`

## File map

| 路径 | 职责 |
|------|------|
| `ops_warm_watchlist_strategy.py` | 策略预热 skipped 壳 |
| `ops_scan_horizon_outlook.py` | 展望扫描 skipped 壳 |
| `ops_catalog` / `ops_runners` / `scheduler_defaults` | 注册 |
| `tests/test_ops_warm_watchlist_strategy.py` 等 | 单测 |
| `docs/product-roadmap.md` / `smoke-checklist.md` | 文档 |

---

### Task 1: `warm_watchlist_strategy_cache` skipped 壳

**Files:**
- Create: `backend/app/services/ops_warm_watchlist_strategy.py`
- Create: `backend/tests/test_ops_warm_watchlist_strategy.py`

**Interfaces:**
- Produces: `warm_watchlist_strategy_cache(db: Session) -> dict[str, Any]`
- Consumes: `save_job_run_meta`

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_ops_warm_watchlist_strategy.py
from unittest.mock import MagicMock, patch

from app.services import ops_warm_watchlist_strategy as m


def test_warm_strategy_skips() -> None:
    db = MagicMock()
    with patch("app.services.ops_warm_watchlist_strategy.save_job_run_meta") as save:
        out = m.warm_watchlist_strategy_cache(db)
    assert out["skipped"] is True
    assert out["success"] is False
    assert "策略引擎" in out["message"]
    save.assert_called_once()
    assert save.call_args.kwargs["last_success"] is False
```

- [ ] **Step 2: 跑测确认失败**

```bash
cd backend && uv run pytest tests/test_ops_warm_watchlist_strategy.py -v
```

Expected: FAIL（模块不存在）

- [ ] **Step 3: 实现**

```python
"""自选策略信号预热占位：zak2 尚未接入策略引擎。"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.services.ops_scheduler import save_job_run_meta

JOB_ID = "warm_watchlist_strategy_cache"
_MESSAGE = "zak2 尚未接入策略引擎，无法预热 watchlist_signal/position cache"


def warm_watchlist_strategy_cache(db: Session) -> dict[str, Any]:
    save_job_run_meta(db, JOB_ID, last_message=_MESSAGE, last_success=False)
    return {"success": False, "skipped": True, "message": _MESSAGE}
```

- [ ] **Step 4: 跑测确认通过**

```bash
cd backend && uv run pytest tests/test_ops_warm_watchlist_strategy.py -q
```

Expected: 1 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/ops_warm_watchlist_strategy.py backend/tests/test_ops_warm_watchlist_strategy.py
git commit -m "$(cat <<'EOF'
feat(ops): 实现 warm_watchlist_strategy_cache 诚实 skipped 壳

尚未接入策略引擎，仅注册可跑占位并写 meta。
EOF
)"
```

---

### Task 2: `scan_horizon_outlook` skipped 壳

**Files:**
- Create: `backend/app/services/ops_scan_horizon_outlook.py`
- Create: `backend/tests/test_ops_scan_horizon_outlook.py`

**Interfaces:**
- Produces: `scan_horizon_outlook(db: Session) -> dict[str, Any]`
- Consumes: `save_job_run_meta`

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_ops_scan_horizon_outlook.py
from unittest.mock import MagicMock, patch

from app.services import ops_scan_horizon_outlook as m


def test_horizon_skips() -> None:
    db = MagicMock()
    with patch("app.services.ops_scan_horizon_outlook.save_job_run_meta") as save:
        out = m.scan_horizon_outlook(db)
    assert out["skipped"] is True
    assert out["success"] is False
    assert "展望" in out["message"] or "扫描" in out["message"]
    save.assert_called_once()
    assert save.call_args.kwargs["last_success"] is False
```

- [ ] **Step 2: 跑测确认失败**

```bash
cd backend && uv run pytest tests/test_ops_scan_horizon_outlook.py -v
```

Expected: FAIL

- [ ] **Step 3: 实现**

```python
"""雷达展望扫描占位：zak2 尚未接入 horizon/predict 管线。"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.services.ops_scheduler import save_job_run_meta

JOB_ID = "scan_horizon_outlook"
_MESSAGE = "zak2 尚未接入雷达展望扫描管线，无法写入 radar_horizon/predict cache"


def scan_horizon_outlook(db: Session) -> dict[str, Any]:
    save_job_run_meta(db, JOB_ID, last_message=_MESSAGE, last_success=False)
    return {"success": False, "skipped": True, "message": _MESSAGE}
```

- [ ] **Step 4: 跑测确认通过**

```bash
cd backend && uv run pytest tests/test_ops_scan_horizon_outlook.py -q
```

Expected: 1 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/ops_scan_horizon_outlook.py backend/tests/test_ops_scan_horizon_outlook.py
git commit -m "$(cat <<'EOF'
feat(ops): 实现 scan_horizon_outlook 诚实 skipped 壳

尚未接入展望管线，仅注册可跑占位并写 meta。
EOF
)"
```

---

### Task 3: 注册 RUNNABLE + cron + 文档 + check

**Files:**
- Modify: `backend/app/services/ops_catalog.py` — `RUNNABLE_JOB_IDS` 加两 id；JobSpec 描述注明占位 skipped
- Modify: `backend/app/services/ops_runners.py` — import + RUNNERS
- Modify: `backend/app/services/scheduler_defaults.py` — DEFAULT_CRON
- Modify: `backend/tests/test_ops_catalog.py`、`test_ops_job_kind.py`、`test_scheduler_defaults.py`（planned 夹具**继续**用 `prefetch_concept_board`）
- Modify: `docs/product-roadmap.md`、`docs/smoke-checklist.md`

**Interfaces:**
- Consumes: Task 1/2 导出函数
- Produces: 两 id ∈ RUNNABLE；RUNNERS 对齐；DEFAULT_CRON 有键

- [ ] **Step 1: 改注册与测试**

`RUNNABLE_JOB_IDS` 增加：
- `"warm_watchlist_strategy_cache"`
- `"scan_horizon_outlook"`

`JobSpec` 描述示例：
- warm：`占位：尚未接入策略引擎（Web 可跑 → skipped）`
- horizon：`占位：尚未接入展望扫描管线（Web 可跑 → skipped）`

`RUNNERS`：
```python
"warm_watchlist_strategy_cache": ops_warm_watchlist_strategy.warm_watchlist_strategy_cache,
"scan_horizon_outlook": ops_scan_horizon_outlook.scan_horizon_outlook,
```

`DEFAULT_CRON`：
```python
"scan_horizon_outlook": {"hour": 18, "minute": 15, "day_of_week": "mon-fri"},
"warm_watchlist_strategy_cache": {"hour": 18, "minute": 45, "day_of_week": "mon-fri"},
```

`test_ops_catalog.py`：断言两 id ∈ RUNNABLE。  
`test_ops_job_kind.py`：两 id == runnable；`prefetch_concept_board` 仍 planned。  
`test_scheduler_defaults.py`：可选显式断言两 cron；依赖 `test_defaults_cover_all_runnable` 即可。

- [ ] **Step 2: 文档**

`product-roadmap.md` 增加完成项，例如：  
`7. ~~Ops planned 第三批~~（已完成 → [spec](...batch3-design.md)）：warm_watchlist_strategy_cache / scan_horizon_outlook 为可跑占位（恒 skipped）`

`smoke-checklist.md`：
- 可跑列表加入两 job  
- 手动跑两项：期望 skipped 文案含策略引擎 / 展望管线  
- cron：horizon 工作日 18:15；warm 工作日 18:45

- [ ] **Step 3: check.sh**

```bash
./scripts/check.sh
```

Expected: pytest 全绿 + frontend build OK

- [ ] **Step 4: Commit**

```bash
git add backend/app/services/ops_catalog.py backend/app/services/ops_runners.py \
  backend/app/services/scheduler_defaults.py backend/tests/test_ops_catalog.py \
  backend/tests/test_ops_job_kind.py backend/tests/test_scheduler_defaults.py \
  docs/product-roadmap.md docs/smoke-checklist.md
git commit -m "$(cat <<'EOF'
feat(ops): 注册策略预热与展望扫描为可跑占位

DEFAULT_CRON 展示；恒 skipped；更新路线图与 smoke。
EOF
)"
```

---

## Spec coverage（自审）

| Spec 要求 | Task |
|-----------|------|
| warm skipped 壳 + message + meta | 1 |
| horizon skipped 壳 + message + meta | 2 |
| RUNNABLE / RUNNERS / DEFAULT_CRON / 文档 / check | 3 |
| 不写 cache；不实现 concept/分钟线 | Global |

无 TBD；message 关键字与 spec 一致。

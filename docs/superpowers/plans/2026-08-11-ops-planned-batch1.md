# Ops planned 首批四 job 升级 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 `sync_suspend_daily`、`sync_disclosure_calendar`、`prefetch_tushare`、`warm_radar_card_snapshots` 升级为可跑 job（默认定时关）。

**Architecture:** 每 job 独立服务模块 + mock 单测；最后统一注册 RUNNABLE / RUNNERS / DEFAULT_CRON；雷达预热复用抽取的合成卡片构建函数。

**Tech Stack:** FastAPI Session、Tushare HTTP（`tushare_client.query`）、pytest mock

**Spec:** `docs/superpowers/specs/2026-08-11-ops-planned-batch1-design.md`

## Global Constraints

- 只改 zak2；不改 zak / vnpy-*；不实现其余 6 个 planned
- 不改 enrich / quote-collector / hard_filters 语义（本刀可不改选股）
- 无 token / 空数据 → skipped + `save_job_run_meta`
- enabled 默认 false；仅加 DEFAULT_CRON
- commit message 简体中文：`<type>(<scope>): <简述>`

## File map

| 路径 | 职责 |
|------|------|
| `ops_sync_suspend.py` | 停牌同步 |
| `ops_sync_disclosure.py` | 披露日历 |
| `ops_prefetch_tushare.py` | 因子缓存 |
| `ops_warm_radar.py` + `radar.py` | 雷达预热 |
| `ops_catalog` / `ops_runners` / `scheduler_defaults` | 注册 |
| `tests/test_ops_sync_suspend.py` 等 | 单测 |
| `docs/product-roadmap.md` / `smoke-checklist.md` | 文档 |

---

### Task 1: `sync_suspend_daily`

**Files:**
- Create: `backend/app/services/ops_sync_suspend.py`
- Create: `backend/tests/test_ops_sync_suspend.py`

**Interfaces:**
- Produces: `sync_suspend_daily(db) -> dict`
- Consumes: `ts.require_token` / `ts.query`；`latest_open_yyyymmdd`；`ts_code_to_tf`

**约定：**
- `cal_date` 存 `YYYY-MM-DD`（与现库一致；由 YYYYMMDD 转换）
- exchange：`SHSE→SSE`、`SZSE→SZSE`、`BJSE→BSE`（与现 suspend 表一致）
- 策略：`DELETE WHERE cal_date=:d` 再批量 INSERT

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_ops_sync_suspend.py
from unittest.mock import MagicMock, patch

from app.services import ops_sync_suspend as m


def test_suspend_skips_without_token() -> None:
    db = MagicMock()
    with patch(
        "app.services.ops_sync_suspend.ts.require_token",
        side_effect=m.ts.TushareNotConfiguredError("未配置 TUSHARE_TOKEN"),
    ), patch("app.services.ops_sync_suspend.save_job_run_meta") as save:
        out = m.sync_suspend_daily(db)
    assert out["skipped"] is True
    save.assert_called_once()


def test_suspend_writes_rows() -> None:
    db = MagicMock()
    rows = [{"ts_code": "000001.SZ", "trade_date": "20260811", "suspend_type": "S"}]
    with patch("app.services.ops_sync_suspend.ts.require_token", return_value="tok"), patch(
        "app.services.ops_sync_suspend.latest_open_yyyymmdd", return_value="20260811"
    ), patch("app.services.ops_sync_suspend.ts.query", return_value=rows), patch(
        "app.services.ops_sync_suspend.save_job_run_meta"
    ):
        out = m.sync_suspend_daily(db)
    assert out["success"] is True
    assert out.get("written", 0) >= 1
    assert db.execute.called
```

- [ ] **Step 2: 跑测确认失败**

`cd backend && uv run pytest tests/test_ops_sync_suspend.py -v` → FAIL

- [ ] **Step 3: 实现**

```python
"""停牌日同步：Tushare suspend_d → app.symbol_suspend_days。"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services import tushare_client as ts
from app.services.ops_scheduler import save_job_run_meta
from app.services.tushare_screener import latest_open_yyyymmdd, ts_code_to_tf

JOB_ID = "sync_suspend_daily"


def _yyyymmdd_to_iso(d: str) -> str:
    s = str(d or "").replace("-", "")[:8]
    if len(s) != 8:
        return str(d or "")
    return f"{s[:4]}-{s[4:6]}-{s[6:8]}"


def _tf_to_symbol_exchange(tf: str) -> tuple[str, str] | None:
    if "." not in tf:
        return None
    exch, sym = tf.split(".", 1)
    mapping = {"SHSE": "SSE", "SZSE": "SZSE", "BJSE": "BSE"}
    return sym, mapping.get(exch, exch)


def sync_suspend_daily(db: Session) -> dict[str, Any]:
    try:
        ts.require_token()
    except ts.TushareNotConfiguredError as exc:
        message = str(exc)
        save_job_run_meta(db, JOB_ID, last_message=message, last_success=False)
        return {"success": False, "skipped": True, "message": message}

    trade_date = latest_open_yyyymmdd(db)
    try:
        rows = ts.query(
            "suspend_d",
            {"trade_date": trade_date, "suspend_type": "S"},
            fields="ts_code,trade_date,suspend_type",
        )
    except Exception as exc:  # noqa: BLE001
        message = f"suspend_d 失败: {exc}"
        save_job_run_meta(db, JOB_ID, last_message=message[:500], last_success=False)
        return {"success": False, "skipped": True, "message": message, "trade_date": trade_date}

    cal_date = _yyyymmdd_to_iso(trade_date)
    payload: list[dict[str, str]] = []
    for item in rows:
        tf = ts_code_to_tf(str(item.get("ts_code") or ""))
        pair = _tf_to_symbol_exchange(tf)
        if not pair:
            continue
        sym, exch = pair
        payload.append(
            {
                "symbol": sym,
                "exchange": exch,
                "cal_date": _yyyymmdd_to_iso(str(item.get("trade_date") or trade_date)),
                "suspend_type": str(item.get("suspend_type") or "S")[:1] or "S",
            }
        )

    if not payload:
        message = f"无停牌数据（trade_date={trade_date}）"
        save_job_run_meta(db, JOB_ID, last_message=message, last_success=False)
        return {"success": False, "skipped": True, "message": message, "trade_date": trade_date}

    db.execute(text("DELETE FROM app.symbol_suspend_days WHERE cal_date = :d"), {"d": cal_date})
    db.execute(
        text(
            """
            INSERT INTO app.symbol_suspend_days (symbol, exchange, cal_date, suspend_type)
            VALUES (:symbol, :exchange, :cal_date, :suspend_type)
            ON CONFLICT (symbol, exchange, cal_date) DO UPDATE
            SET suspend_type = EXCLUDED.suspend_type
            """
        ),
        payload,
    )
    db.commit()
    message = f"停牌同步 {len(payload)} 条（cal_date={cal_date}）"
    save_job_run_meta(db, JOB_ID, last_message=message, last_success=True)
    return {"success": True, "skipped": False, "message": message, "written": len(payload), "trade_date": trade_date}
```

（若 `ts.query` 抛 `HTTPException`，测试里可用 side_effect 或 catch `Exception` 已覆盖。）

- [ ] **Step 4: 测试通过**

`cd backend && uv run pytest tests/test_ops_sync_suspend.py -q`

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/ops_sync_suspend.py backend/tests/test_ops_sync_suspend.py
git commit -m "$(cat <<'EOF'
feat(ops): 实现 sync_suspend_daily 停牌日同步

Tushare suspend_d 写入 symbol_suspend_days，供硬过滤使用。
EOF
)"
```

---

### Task 2: `sync_disclosure_calendar`

**Files:**
- Create: `backend/app/services/ops_sync_disclosure.py`
- Create: `backend/tests/test_ops_sync_disclosure.py`

**Interfaces:**
- Produces: `sync_disclosure_calendar(db) -> dict`
- `end_date`：取「不晚于今天的最近季末」YYYYMMDD（3/6/9/12 月最后一天）

- [ ] **Step 1: 失败测试**

```python
from unittest.mock import MagicMock, patch
from app.services import ops_sync_disclosure as m

def test_disclosure_skips_without_token() -> None:
    db = MagicMock()
    with patch(
        "app.services.ops_sync_disclosure.ts.require_token",
        side_effect=m.ts.TushareNotConfiguredError("未配置 TUSHARE_TOKEN"),
    ), patch("app.services.ops_sync_disclosure.save_job_run_meta"):
        out = m.sync_disclosure_calendar(db)
    assert out["skipped"] is True

def test_disclosure_upserts() -> None:
    db = MagicMock()
    rows = [{
        "ts_code": "000001.SZ",
        "end_date": "20260630",
        "pre_date": "20260830",
        "ann_date": "",
        "actual_date": "",
    }]
    with patch("app.services.ops_sync_disclosure.ts.require_token", return_value="t"), patch(
        "app.services.ops_sync_disclosure.latest_report_end_yyyymmdd", return_value="20260630"
    ), patch("app.services.ops_sync_disclosure.ts.query", return_value=rows), patch(
        "app.services.ops_sync_disclosure.save_job_run_meta"
    ):
        out = m.sync_disclosure_calendar(db)
    assert out["success"] is True
    assert out.get("written", 0) >= 1
```

- [ ] **Step 2: FAIL 确认**

- [ ] **Step 3: 实现要点**

```python
def latest_report_end_yyyymmdd(today: date | None = None) -> str:
    """不晚于 today 的最近财报季末（3/6/9/12 月最后一天）。"""
    ...

def sync_disclosure_calendar(db: Session) -> dict[str, Any]:
    # require_token；query disclosure_date end_date=...
    # UPSERT PK (ts_code, end_date)；fetched_at=isoformat
```

- [ ] **Step 4: PASS**

- [ ] **Step 5: Commit** `feat(ops): 实现 sync_disclosure_calendar 披露计划同步`

---

### Task 3: `prefetch_tushare`

**Files:**
- Create: `backend/app/services/ops_prefetch_tushare.py`
- Create: `backend/tests/test_ops_prefetch_tushare.py`

**Interfaces:**
- Produces: `prefetch_tushare(db) -> dict`
- 写 `daily_basic`（必选）+ `moneyflow`（失败记 notes 仍可成功若 basic 成功）

- [ ] **Step 1: 测试** — 无 token skipped；basic 成功 upsert；moneyflow 失败仍 success 带 notes

- [ ] **Step 2–4: 实现**

```python
# 使用 fetch_daily_basic_rows / fetch_moneyflow_rows
# INSERT ... ON CONFLICT (dataset, trade_date) DO UPDATE SET payload, fetched_at
# payload = json.dumps(rows, ensure_ascii=False)
```

- [ ] **Step 5: Commit** `feat(ops): 实现 prefetch_tushare 本地因子缓存`

---

### Task 4: `warm_radar_card_snapshots` + 抽取合成

**Files:**
- Modify: `backend/app/services/radar.py`
- Create: `backend/app/services/ops_warm_radar.py`
- Create: `backend/tests/test_ops_warm_radar.py`
- Modify: 现有 `tests/test_radar*.py` 若因抽取破坏则修

**Interfaces:**
- Produces: `build_synthesized_cards(db) -> list[RadarCardOut]`；`warm_radar_card_snapshots(db) -> dict`
- `list_radar_cards` 改为调用 `build_synthesized_cards`

- [ ] **Step 1: 测试**

```python
def test_warm_upserts_cards() -> None:
    db = MagicMock()
    card = MagicMock()
    card.card_id = "leader_pick"
    card.title = "选股·龙头"
    card.subtitle = ""
    card.rows = []
    card.empty_message = ""
    card.model_dump = lambda: {
        "title": "选股·龙头", "subtitle": "", "rows": [], "empty_message": ""
    }
    # 或用真实 RadarCardOut
    with patch("app.services.ops_warm_radar.build_synthesized_cards", return_value=[...]), patch(
        "app.services.ops_warm_radar.save_job_run_meta"
    ):
        out = warm_radar_card_snapshots(db)
    assert out["success"] is True
```

- [ ] **Step 2–4: 实现**

`radar.py`：

```python
def build_synthesized_cards(db: Session) -> list[RadarCardOut]:
    return [
        _synth_leader_pick(db),
        _synth_limit_ladder(db),
        _synth_sector_hot(db),
        _synth_change_top(),
    ]

def list_radar_cards(db: Session) -> list[RadarCardOut]:
    cached = {c.card_id: c for c in _from_cache(db)}
    synthesized = build_synthesized_cards(db)
    ...
```

`ops_warm_radar.py`：对每张卡 upsert `cache.radar_card_snapshot`；`variant_key=''`；`computed_at` ISO；`payload_json` 含 title/subtitle/rows/empty_message。

- [ ] **Step 5: Commit** `feat(ops): 实现雷达卡片预热并抽取合成构建`

---

### Task 5: 注册 RUNNABLE + cron + 文档

**Files:**
- Modify: `ops_catalog.py`、`ops_runners.py`、`scheduler_defaults.py`
- Modify: `tests/test_ops_catalog.py`、`tests/test_ops_job_kind.py`（及仍用 planned 夹具的测试：继续用 `prefetch_moneyflow`）
- Modify: `docs/product-roadmap.md`、`docs/smoke-checklist.md`

**DEFAULT_CRON：**

```python
"sync_suspend_daily": {"hour": 17, "minute": 40, "day_of_week": "mon-fri"},
"sync_disclosure_calendar": {"hour": 8, "minute": 30, "day_of_week": "mon"},
"prefetch_tushare": {"hour": 15, "minute": 30, "day_of_week": "mon-fri"},
"warm_radar_card_snapshots": {"hours": [9, 10, 14], "minute": 20, "day_of_week": "mon-fri"},
```

- [ ] **Step 1: 扩展 catalog/job_kind 断言四 id ∈ RUNNABLE**

- [ ] **Step 2: 接线 + JobSpec 描述微调（可选）**

- [ ] **Step 3:**

```bash
cd backend && uv run pytest tests/test_ops_sync_suspend.py tests/test_ops_sync_disclosure.py \
  tests/test_ops_prefetch_tushare.py tests/test_ops_warm_radar.py \
  tests/test_ops_catalog.py tests/test_ops_job_kind.py tests/test_ops_job_guards.py -q
./scripts/check.sh
```

- [ ] **Step 4: Commit**

```bash
git commit -m "$(cat <<'EOF'
feat(ops): 注册停牌/披露/因子预拉/雷达预热为可跑任务

默认定时展示但开关默认关；更新路线图与 smoke。
EOF
)"
```

---

## Spec coverage

| Spec | Task |
|------|------|
| sync_suspend_daily | 1 |
| sync_disclosure_calendar | 2 |
| prefetch_tushare | 3 |
| warm_radar_card_snapshots | 4 |
| RUNNABLE / cron / 文档 | 5 |
| 其余 6 planned 不动 | 遵守 |

## 执行交接

Plan：`docs/superpowers/plans/2026-08-11-ops-planned-batch1.md`

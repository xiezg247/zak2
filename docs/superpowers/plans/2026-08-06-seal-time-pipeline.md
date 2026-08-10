# 封板时间深度 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development 或 executing-plans。步骤用 `- [ ]` 跟踪。

**Goal:** Tushare `limit_list_d` → PG `app.limit_list_daily` → 龙头评分含 `seal_time`，雷达/Hub/共振展示封板时刻。

**Architecture:** 纯函数 `seal_time` + sync job upsert 日表；`limit_list_store` 提供 map/懒拉；`leader_screen` / `radar` attach；前端展示 label。

**Tech Stack:** FastAPI、SQLAlchemy/text SQL、Tushare HTTP、Vue、pytest。

**Spec:** `docs/superpowers/specs/2026-08-06-seal-time-pipeline-design.md`

## Global Constraints

- 只改 zak2，不改 zak / vnpy-*
- 不接 TickFlow；无 token / 拉取失败静默降级
- 不做阶段自适应权重、权重 UI、改共振权重
- Commit 仅在用户明确要求时执行（本计划步骤不自动 commit）

## File map

| 文件 | 职责 |
|------|------|
| `backend/app/services/seal_time.py` | `parse_clock_minutes` / `seal_time_score` / `format_seal_time_label` |
| `backend/app/models/market.py` | `LimitListDaily` ORM |
| `backend/app/services/ops_sync_limit_list.py` | DDL ensure + Tushare sync upsert |
| `backend/app/services/limit_list_store.py` | `load_first_time_map`、懒拉、`attach_first_time` |
| `backend/app/services/leader_screen.py` | 权重 + 打分注入 seal_time |
| `backend/app/services/radar.py` | 连板梯队行补 first_time |
| `backend/app/services/radar_resonance.py` | 共振条目可选 seal_time_label |
| `backend/app/api/v1/ops.py` + `ops_catalog.py` | 注册 `sync_limit_list` |
| `backend/app/api/v1/market.py` + schemas | `GET /market/limit-list` |
| `frontend` RadarView / ScreenerHub / market api | 展示 |
| `docs/gap-vs-desktop.md` / `smoke-checklist.md` | 文档 |

---

### Task 1: seal_time 纯函数 + 单测

**Files:**
- Create: `backend/app/services/seal_time.py`
- Create: `backend/tests/test_seal_time.py`

**Produces:**
- `parse_clock_minutes(text: str) -> int | None`
- `seal_time_score(first_time: str) -> float`
- `format_seal_time_label(first_time: str) -> str`

- [ ] **Step 1: 写失败测试**

```python
from app.services.seal_time import format_seal_time_label, parse_clock_minutes, seal_time_score

def test_parse_and_score_bands():
    assert parse_clock_minutes("0935") == 9 * 60 + 35
    assert seal_time_score("0930") == 1.0
    assert seal_time_score("1100") == 0.7
    assert seal_time_score("1400") == 0.5
    assert seal_time_score("1501") == 0.0
    assert seal_time_score("") == 0.0
    assert format_seal_time_label("0935") == "09:35 封板"
```

时段对齐桌面：`565–630→1.0`，`630–810→0.7`，`810–900→0.5`。

- [ ] **Step 2:** `cd backend && uv run pytest tests/test_seal_time.py -q` → FAIL（模块不存在）

- [ ] **Step 3: 实现 `seal_time.py`**（逻辑同 zak `trading/signals/seal_time.py`，不 import vnpy）

- [ ] **Step 4:** 同上 pytest → PASS

---

### Task 2: 模型 + sync_limit_list + store

**Files:**
- Modify: `backend/app/models/market.py`、`backend/app/models/__init__.py`
- Create: `backend/app/services/ops_sync_limit_list.py`
- Create: `backend/app/services/limit_list_store.py`
- Modify: `backend/app/services/ops_catalog.py`、`backend/app/api/v1/ops.py`
- Modify: `backend/tests/test_ops_catalog.py`
- Create: `backend/tests/test_limit_list_store.py`

**Produces:**
- `sync_limit_list(db) -> dict`
- `ensure_limit_list_table(db) -> None`
- `load_first_time_map(db, trade_date: str | None = None, *, lazy_fetch: bool = True) -> dict[str, str]`
- `attach_first_time_fields(rows: list[dict], first_time_map: dict[str, str]) -> None`（就地写 `first_time` / `seal_time_score` / `seal_time_label`；键可用 `vt_symbol` 或 `tf_symbol`）

- [ ] **Step 1: ORM `LimitListDaily`**

主键 `(trade_date, vt_symbol)`；列见 spec。表名 `limit_list_daily`（schema `app` 经 search_path）。

- [ ] **Step 2: `ops_sync_limit_list.py`**

```python
JOB_ID = "sync_limit_list"
DDL = """
CREATE TABLE IF NOT EXISTS app.limit_list_daily (
  trade_date text NOT NULL,
  vt_symbol text NOT NULL,
  ts_code text NOT NULL DEFAULT '',
  name text NOT NULL DEFAULT '',
  limit_times double precision NOT NULL DEFAULT 0,
  first_time text NOT NULL DEFAULT '',
  last_time text NOT NULL DEFAULT '',
  fd_amount double precision NOT NULL DEFAULT 0,
  open_times double precision NOT NULL DEFAULT 0,
  strth double precision NOT NULL DEFAULT 0,
  updated_at text NOT NULL DEFAULT '',
  PRIMARY KEY (trade_date, vt_symbol)
)
"""
```

- 调 `ts.query("limit_list_d", {"trade_date": td, "limit_type": "U"}, fields="ts_code,trade_date,name,limit_times,first_time,last_time,fd_amount,open_times,strth")`
- `ts_code` → `vt_symbol` 用现有 `tushare_screener.ts_code_to_tf`
- upsert `ON CONFLICT DO UPDATE`
- 默认最近 1 个交易日（`latest_open_yyyymmdd`）；env `LIMIT_LIST_SYNC_DAYS` 可扩到 ≤5
- 无 token：返回 `success=False` + 中文 message（与其它 Tushare job 一致风格）

- [ ] **Step 3: 注册 Ops**

`RUNNABLE_JOB_IDS` + `JOB_SPECS` + `_RUNNERS["sync_limit_list"]`；`test_ops_catalog` 断言含 `sync_limit_list`。

- [ ] **Step 4: `limit_list_store.py`**

从 PG 读 map；若空且 `lazy_fetch` 且有 token，调 sync 当日后再读。

- [ ] **Step 5: 单测** mock `ts.query`，内存/SQLite 或 mock `db.execute`；至少测 map 与 `attach_first_time_fields`。

- [ ] **Step 6:** `uv run pytest tests/test_ops_catalog.py tests/test_limit_list_store.py -q` → PASS

---

### Task 3: leader_screen 接入 seal_time

**Files:**
- Modify: `backend/app/services/leader_screen.py`
- Modify: `backend/tests/test_leader_screen.py`

**Consumes:** `seal_time_score`、`load_first_time_map`、`format_seal_time_label`  
**Produces:** 结果行含 `first_time` / `seal_time_score` / `seal_time_label`；权重见下。

- [ ] **Step 1: 更新权重**

```python
_WEIGHTS = {
    "limit_times": 0.28,
    "seal_quality": 0.16,
    "amount_rank": 0.16,
    "seal_time": 0.12,
    "net_mf": 0.15,
    "sector_strength": 0.13,
}
```

- [ ] **Step 2: `compute_leader_score(..., seal_time: float = 0.0)`** 纳入加权。

- [ ] **Step 3: `rank_leader_pool` / `run_leader_screen` / `synth_leader_pick_rows`**

有 `db` 时 `load_first_time_map(db)`；按 `row.symbol` 取分；结果 dict 写出字段；`_hit_reason` 可附带 label。

- [ ] **Step 4: 单测** 同一 QuoteRow，有 `first_time=0930` 时 score > 无时间。

- [ ] **Step 5:** `uv run pytest tests/test_leader_screen.py -q` → PASS

---

### Task 4: 雷达 / 共振 / limit-list API

**Files:**
- Modify: `backend/app/services/radar.py`（`_synth_limit_ladder`）
- Modify: `backend/app/services/radar_resonance.py` + schema `RadarResonanceEntry`
- Modify: `backend/app/schemas/market.py`、`backend/app/api/v1/market.py`
- Create/Modify: `backend/tests/test_limit_list_api.py`（或并入现有 market 测）

- [ ] **Step 1: 连板梯队** 对有 `vt_symbol` 的行 attach first_time 字段。

- [ ] **Step 2: 共振** `RadarResonanceEntry` 增加可选 `seal_time_label: str = ""`；`compute_resonance` 接受 optional map 或内部查库。

- [ ] **Step 3: API**

`GET /api/v1/market/limit-list?trade_date=` → `{ trade_date, total, rows: [...] }`  
无数据返回空列表不 500。

- [ ] **Step 4:** 相关 pytest → PASS

---

### Task 5: 前端 + 文档 + 全量验收

**Files:**
- Modify: `frontend/src/api/market.ts`（可选 limit-list 类型；共振类型加 label）
- Modify: `frontend/src/views/RadarView.vue`
- Modify: `frontend/src/views/ScreenerHubView.vue`
- Modify: `docs/gap-vs-desktop.md`、`docs/smoke-checklist.md`

- [ ] **Step 1: Hub** 龙头行展示 `seal_time_label` 或 `first_time`（有则显示）。

- [ ] **Step 2: Radar** 明细与共振侧栏有则显示封板时刻。

- [ ] **Step 3: 文档** 缺口表「封板时间深度」改为有/薄；smoke 增加 Ops `sync_limit_list` 与 UI 检查项。

- [ ] **Step 4: 验收**

```bash
cd backend && uv run pytest -q
cd ../frontend && npm run build
```

Expected: pytest 全绿；build 成功。

---

## Spec coverage

| Spec 项 | Task |
|---------|------|
| seal_time 纯函数 | 1 |
| 表 + sync + 懒拉 | 2 |
| 龙头权重与字段 | 3 |
| 雷达梯队 / 共振 / limit-list API | 4 |
| 前端 + gap/smoke | 5 |
| 非目标（TickFlow 等） | 不实现 |

## Self-review

- 无 TBD；权重与 spec 一致  
- `ts_code_to_tf` 复用已有，不新造映射  
- Commit 步骤已按用户规则省略自动提交  

# 后端 Phase 4（screener / market / backtest）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 按域将 `screener`、`market`（含 radar/emotion）、`backtest` 迁入 `app.domains.*`，service 层改用 `AppError`，router 变薄且零直连 Repository；旧路径 thin re-export。

**Architecture:** 三波可独立验收（对应 spec「按域分 PR」），同一 feature 分支连续落地：Wave A screener → Wave B market/radar/emotion → Wave C backtest。`ops.arq_jobs` / worker 仅改 import 兼容壳，不重写拓扑。

**Tech Stack:** FastAPI、SQLAlchemy、`AppError`、pytest、既有 ARQ enqueue。

**Spec:** [docs/superpowers/specs/2026-08-20-backend-architecture-refactor-design.md](../specs/2026-08-20-backend-architecture-refactor-design.md) Phase 4。

## Global Constraints

- 对外 REST 路径、JWT、Redis 键、ARQ job_id / `SCREENER_FUNCS` / `BACKTEST_FUNCS` 名不变
- commit 简体中文 `<type>(<scope>): <简述>`
- domain router **禁止** `HTTPException` 与直连 `*Repository`
- domain service **禁止** FastAPI `HTTPException`（→ `AppError`）
- domain **禁止** import `app.api.v1`；`models` 不搬
- 旧 `app.services.{screener,market,radar,emotion,backtest}`、`app.repositories.*`、`app.schemas.*`、`app.api.v1.*` 保留 re-export
- 不重写选股/回测算法；不迁 `ops` worker 拓扑（Phase 5）

---

## Wave A — screener

### Task 1: 迁 schemas + repository + services/screener（AppError）

**Files:**
- Create: `domains/screener/__init__.py`、`schemas.py`、`repository.py`、以及原 `services/screener/*.py` 全部迁入（保持文件名）
- Replace: `schemas/screener.py`、`repositories/screener.py`、`services/screener/*` → re-export
- Modify: 测试中 `pytest.raises(HTTPException)` 改为对应 `AppError`（`rg HTTPException backend/tests/test_*screen* backend/tests/test_*recipe* backend/tests/test_*pattern* backend/tests/test_*resonance* backend/tests/test_*leader*`）

**映射：** 400→`ValidationFailed`，404→`NotFound`，502→`UpstreamFailed`，503→`Unavailable`（若有）。

- [ ] **Step 1:** 复制 `schemas/screener.py` → `domains/screener/schemas.py`
- [ ] **Step 2:** 复制 `repositories/screener.py` → `domains/screener/repository.py`，schemas import 改域内
- [ ] **Step 3:** 逐文件复制 `services/screener/*.py` → `domains/screener/`，改内部互引为 `app.domains.screener.*`；全局替换 `HTTPException` 为 AppError 子类；删除 `from fastapi import HTTPException`
- [ ] **Step 4:** 旧路径显式 re-export（列出被外部 import 的符号；可用 `rg "from app.services.screener"`）
- [ ] **Step 5:** 更新相关测试断言
- [ ] **Step 6:** 跑测

```bash
cd backend && uv run pytest \
  tests/test_pattern_screen.py tests/test_pattern_rules.py \
  tests/test_recipe_weights.py tests/test_resonance_screen.py \
  tests/test_leader_screen.py tests/test_screener_result_compat.py \
  tests/test_ops_auto_screen.py -v
```

- [ ] **Step 7: Commit** `refactor(screener): 选股服务与仓库迁入 domains 并改用 AppError`

---

### Task 2: ScreenerService + 薄 router

**Files:**
- Create: `domains/screener/service.py`、`router.py`
- Replace: `api/v1/screener.py` → re-export
- Modify: patch `api.v1.screener` 的测试（若有）

**Interfaces:** `ScreenerService` 承接现 router 中 scheme/recipe CRUD、weights、runs 查询中的 404/400；run/enqueue 仍调 `enqueue_app_job` + 域内 engine 入口。Router 只 Depends + service/模块函数。

- [ ] **Step 1:** 把 `api/v1/screener.py` 行为迁入 `service.py` + 薄 `router.py`（路径/前缀不变；现 router 无 prefix，路径含 `/screener/...`）
- [ ] **Step 2:** router 零 `HTTPException` / 零 `Repository`
- [ ] **Step 3:**

```bash
(rg "HTTPException|Repository" app/domains/screener/router.py && exit 1 || echo ok)
wc -l app/domains/screener/router.py
uv run pytest tests/test_recipe_weights.py tests/test_screener_result_compat.py tests/test_ops_auto_screen.py tests/test_pattern_screen.py -v
```

- [ ] **Step 4: Commit** `refactor(screener): API 迁入 domains 薄 router`

---

## Wave B — market + radar + emotion

### Task 3: 迁 market/radar/emotion 包 + schemas.market

**Files:**
- Create: `domains/market/`（overview、sector、quotes 相关被 screener/watchlist 依赖的模块：**quotes/bars/fundamentals/suspend/stock_industry 等若被多域依赖，可留 `services/market` 仅迁 overview/sector/limit_list 等 market 页专用；为减少断裂，本 Task 将整个 `services/market`、`services/radar`、`services/emotion` 迁到 `domains/market/`、`domains/radar/`、`domains/emotion/`，旧路径 re-export）
- Create: `domains/market/schemas.py` ← `schemas/market.py`
- Replace HTTPException → AppError in moved modules
- Update tests asserting HTTPException under market/radar/emotion/fundamentals

- [ ] **Step 1–4:** 搬迁三包 + schemas；AppError 替换；re-export；更新测试
- [ ] **Step 5:** 

```bash
uv run pytest tests/test_emotion_cycle.py tests/test_emotion_thresholds.py \
  tests/test_emotion_thresholds_api.py tests/test_fundamentals.py \
  tests/test_ops_warm_market.py tests/test_radar_resonance_funnel.py \
  tests/test_radar_predict_score.py -v --tb=line
```

（缺文件则跳过；以 `ls tests/test_*emotion* tests/test_*radar* tests/test_*sector* tests/test_*market*` 为准跑齐）

- [ ] **Step 6: Commit** `refactor(market): market/radar/emotion 迁入 domains 并改用 AppError`

---

### Task 4: market 薄 router

**Files:**
- Create: `domains/market/router.py`（可 include 或单文件；路径仍为 `/market/*` `/sectors/*` `/radar/*`）
- Replace: `api/v1/market.py` → re-export
- 将 router 内 `HTTPException` 改为域 service 抛 AppError

- [ ] **Step 1–3:** 薄 router；分层检查；相关 API 测试
- [ ] **Step 4: Commit** `refactor(market): API 迁入 domains 薄 router`

---

## Wave C — backtest

### Task 5: 迁 backtest schemas/repo/services + 薄 router

**Files:**
- Create: `domains/backtest/{schemas,repository,*.py from services/backtest,service,router}.py`
- Replace: 旧路径 re-export；`api/v1/backtest.py` re-export
- `_validate_ma_windows` → `ValidationFailed`；其它 HTTPException 按表映射

- [ ] **Step 1–4:** 搬迁 + AppError + 薄 router + 测试（`ls tests/test_*backtest*`）
- [ ] **Step 5: Commit** `refactor(backtest): 回测域迁入 domains 并由薄 router 承接`

---

### Task 6: domains README + 总回归

- [ ] **Step 1:** README「已迁入」追加 screener / market+radar+emotion / backtest（Phase 4）
- [ ] **Step 2:**

```bash
cd backend && uv run pytest \
  tests/test_pattern_screen.py tests/test_recipe_weights.py \
  tests/test_screener_result_compat.py tests/test_ops_auto_screen.py \
  tests/test_emotion_cycle.py tests/test_fundamentals.py \
  tests/test_backtest_api_validate.py tests/test_backtest_bars_interval.py \
  tests/test_auth_api.py tests/test_channels_api.py tests/test_watchlist_groups.py -v
```

- [ ] **Step 3: Commit** `docs(domains): 标注 Phase 4 三域已迁入`

---

## Spec coverage

| 域 | Tasks |
|----|-------|
| screener | 1–2 |
| market/radar/emotion | 3–4 |
| backtest | 5 |
| 文档 | 6 |

## Out of scope

- ops/worker 重构（Phase 5）
- 拆除兼容壳（Phase 6）
- 改前端 / 算法重写

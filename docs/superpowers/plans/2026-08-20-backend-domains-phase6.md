# 后端 Phase 6（拆除兼容壳）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 拆除 Phase 1–5 迁移期间保留的全部兼容壳（thin re-export / `sys.modules` 别名），将所有内部消费者指向 `app.domains.*`，实现「无双路径实现」。更新 `docs/architecture-p1.md`。

**Architecture:** 按域分批拆壳，每域独立验收：先修域内双路径漂移，再改 app 内消费者（services/ops、services/ai、services/team、worker、main、ws 等）与 tests，最后删除该域 shim。删除顺序遵循「先改消费者、后删壳」，保证每个 commit 全量测试绿。

**Tech Stack:** FastAPI、SQLAlchemy、`AppError`、pytest。

**Spec:** [docs/superpowers/specs/2026-08-20-backend-architecture-refactor-design.md](../specs/2026-08-20-backend-architecture-refactor-design.md) Phase 6。

## 现状盘点（2026-08-21，Base 32f156e）

待删 shim（约 70 个文件，全部为纯转发）：

| 组 | 路径 |
|----|------|
| services 包 | `app/services/{market,screener,radar,emotion,backtest,content,notify,plan}/`（`sys.modules[__name__] = 域模块`）、`app/services/login_guard.py` |
| repositories | `app/repositories/{user,channel,watchlist,positions,signal_panel,screener,backtest,auto_schedule}.py` |
| schemas | `app/schemas/{auth,channel,watchlist,content,screener,market,backtest,auto_schedule}.py` |
| api/v1 | `app/api/v1/{auth,channels,content,watchlist,screener,market,backtest,auto_schedules}.py` |

**保留的真实现（不删）：** `app/services/{ai,ops,quote_collect,strategy,team}`、`app/services/symbols.py`、`app/services/zak_import.py`、`app/repositories/{base,chat,pagination}.py`、`app/schemas/{chat,common,ops,team}.py`、`app/api/v1/{ai,jobs,ops,ws}.py`、`app/api/v1/__init__.py`（改为直连 domains router）。

**消费者规模：** 约 328 行旧路径 import（app 内 + tests），主要分布：`services.market`(112)、`services.screener`(34)+`schemas.screener`(21)、`services.emotion`(23)、`services.backtest`(19)+`schemas.backtest`(7)、`services.radar`(17)、`repositories.positions`(13)、`services.ops.auto_schedule`(13)、`schemas.market`(13)、`repositories.screener`(12)、`repositories.channel`(10，全在 test_channels_api)。

## Global Constraints

- 对外 REST 路径、JWT、Redis 键、ARQ job_id / `SCREENER_FUNCS` / `BACKTEST_FUNCS` / 消息语义不变
- commit 简体中文 `<type>(<scope>): <简述>`
- **删除某 shim 前，其全部消费者（app + tests）必须已改到 `app.domains.*`**；每个 commit 跑全量回归绿
- 删除后全局扫描：`rg "app.services.(market|screener|radar|emotion|backtest|content|notify|plan|login_guard)|app.repositories.(user|channel|watchlist|positions|signal_panel|screener|backtest|auto_schedule)|app.schemas.(auth|channel|watchlist|content|screener|market|backtest|auto_schedule)"` 零命中
- 域间引用一律 `app.domains.*`；`services/ops`、`services/ai`、`services/team`、`worker` 等真实现可 import `app.domains.*`（允许单向）
- `app.repositories.base` / `pagination` 横切保留，域 repository 继续依赖它们
- 不改 REST 路径 / 算法 / worker 拓扑；不新建域

---

## Wave A — 双路径收口 + 小域拆壳

### Task 1: 修复 domains 内双路径漂移

**Files:** `app/domains/watchlist/{market_views,enrich}.py`、`app/domains/radar/{radar_predict,cards}.py`、`app/domains/market/{bars,fundamentals}.py`、`app/domains/screener/{engine,reference_peer,leader_screen,pattern_screen,hard_filters,resonance_screen}.py`、`app/domains/content/{notes,notify_log}.py`（14 个文件）

**做法：** 将域内旧路径 import 全部改 `app.domains.*`：
- `app.services.market.{quotes,bars,fundamentals,suspend,stock_industry,overview,seal_time,limit_list_store,tushare_client,tushare_screener}` → `app.domains.market.*`
- `app.services.radar.cards` → `app.domains.radar.cards`；`app.services.radar.radar_resonance` → `app.domains.radar.radar_resonance`
- `app.services.emotion.emotion_cycle` → `app.domains.emotion.emotion_cycle`
- `app.services.screener.leader_screen` → `app.domains.screener.leader_screen`（radar/cards 内 lazy import）
- `app.repositories.watchlist` → `app.domains.watchlist.repository`（resolve_symbol_pair）
- `app.schemas.watchlist` → `app.domains.watchlist.schemas`（BarOut/BarsResponse/DisclosureOut/FinancialSnapshotOut/FinancialSyncOut/FundamentalsOut/NotifyLogItem/NotifyLogOut）

**验收：** 全量回归绿；`rg "app.services.|app.repositories.|app.schemas." app/domains` 零命中。

```bash
cd backend && uv run pytest -q --tb=short
```

**Commit:** `refactor(domains): 域内旧路径引用全部改走 app.domains`

### Task 2: auth + channels 拆壳

**Files 删除:** `app/services/login_guard.py`、`app/services/notify/{delivery,feishu}.py`、`app/schemas/auth.py`、`app/schemas/channel.py`、`app/repositories/user.py`、`app/repositories/channel.py`、`app/api/v1/auth.py`、`app/api/v1/channels.py`

**改消费者：** `api/v1/__init__.py`（auth/channels router 直连 domains）、`app/services/ops/auto_screen.py`（notify.delivery 若引用）、其余 `rg "app.services.notify|app.services.login_guard|app.schemas.auth|app.schemas.channel|app.repositories.user|app.repositories.channel|app.api.v1.auth|app.api.v1.channels"` 命中处（tests 的 patch 目标改 domains，如 `test_channels_api.py` 的 `app.repositories.channel` → `app.domains.channels.repository`）。

**测试：** `uv run pytest tests/test_login_guard.py tests/test_auth_api.py tests/test_channels_api.py tests/test_notify_feishu.py tests/test_notify_delivery.py -v --tb=line`

**Commit:** `refactor(domains): 拆除 auth/channels 域兼容壳`

---

## Wave B — 核心选股/行情域拆壳

### Task 3: screener 拆壳

**Files 删除:** `app/services/screener/`（11 文件 + `__init__.py`）、`app/schemas/screener.py`、`app/repositories/screener.py`、`app/api/v1/screener.py`

**改消费者：** `app/services/ops/auto_screen.py`、`app/worker/tasks_screener.py`、tests（`rg "app.services.screener|app.schemas.screener|app.repositories.screener"` 全部改 domains）、`api/v1/__init__.py`（screener router 直连）。

**注意：** `services/ops/arq_jobs.py` 的 `SCREENER_FUNCS` 名与 `screener/service.py` 引用 `app.services.ops.arq_jobs` 不变（横切）。

**测试：** screener 相关 + 全量。

```bash
cd backend && uv run pytest -q --tb=short
```

**Commit:** `refactor(domains): 拆除 screener 域兼容壳`

### Task 4: market + radar + emotion 拆壳

**Files 删除:** `app/services/market/`（17）、`app/services/radar/`（5）、`app/services/emotion/`（4）、`app/schemas/market.py`、`app/api/v1/market.py`

**改消费者（最多，约 160 行）：** `app/services/ops/*`（sync_universe/sync_calendar/sync_suspend/sync_sector/sync_limit_list/sync_stock_industry/sync_watchlist_financials/sync_disclosure/enrich_quotes/fill_focus_pool_minute/prefetch_tushare/prefetch_moneyflow/scan_horizon_outlook/bars_fill/warm_market/warm_radar/health）、`app/services/ai/*`（ai_tools/ai_read_tools/ai_context）、`app/services/team/team_prefetch.py`、`app/services/quote_collect/universe.py`、`app/services/strategy/strategy_board.py`、`app/main.py`、`app/api/v1/ws.py`、tests、`api/v1/__init__.py`（market router 直连）。

**映射参考：** `from app.services.market import tushare_client as ts` → `from app.domains.market import tushare_client as ts`；`from app.services.market.quotes import get_quote_store` → `from app.domains.market.quotes import get_quote_store`；`from app.schemas.market import ...` → `from app.domains.market.schemas import ...`；radar/emotion 同理。

**测试：** market/radar/emotion 相关 + 全量。

```bash
cd backend && uv run pytest -q --tb=short
```

**Commit:** `refactor(domains): 拆除 market/radar/emotion 域兼容壳`

---

## Wave C — 业务域拆壳

### Task 5: watchlist + content + plan 拆壳

**Files 删除:** `app/repositories/{watchlist,positions,signal_panel}.py`、`app/schemas/watchlist.py`、`app/services/content/`（3）、`app/schemas/content.py`、`app/services/plan/`（2）、`app/api/v1/{watchlist,content}.py`

**改消费者：** `app/services/ai/*`、`app/services/ops/*`、`app/services/team/*`、`worker/*`、tests 中 `app.repositories.watchlist`、`app.schemas.watchlist`、`app.services.content`、`app.services.plan`、`app.schemas.content` 命中处；`api/v1/__init__.py`（watchlist/content router 直连）。

**测试：** watchlist/content 相关 + 全量。

```bash
cd backend && uv run pytest -q --tb=short
```

**Commit:** `refactor(domains): 拆除 watchlist/content/plan 域兼容壳`

### Task 6: backtest + auto_schedules 拆壳

**Files 删除:** `app/services/backtest/`（7）、`app/schemas/backtest.py`、`app/repositories/backtest.py`、`app/api/v1/backtest.py`、`app/services/ops/auto_schedule.py`、`app/services/ops/auto_schedule_time.py`、`app/schemas/auto_schedule.py`、`app/repositories/auto_schedule.py`、`app/api/v1/auto_schedules.py`

**改消费者：** `app/worker/tasks_backtest.py`、`app/worker/backtest_subprocess.py`、`app/services/ops/embedded_scheduler.py`、tests（`test_auto_schedule_{poll,time,task}.py` 的旧路径 import、`test_backtest*.py` 等）；`api/v1/__init__.py`（backtest/auto_schedules router 直连）。

**测试：** backtest + auto_schedules 相关 + 全量。

```bash
cd backend && uv run pytest -q --tb=short
```

**Commit:** `refactor(domains): 拆除 backtest/auto_schedules 域兼容壳`

---

## Wave D — 收尾

### Task 7: 全局扫尾 + 文档更新

- **Step 1:** 全局扫描确认零旧路径残留（约束中的 rg 命令零命中）；`git rm` 确认无遗漏 shim（`find app -name '*.py' | xargs rg -l "sys.modules\[__name__\]|兼容壳"` 仅剩 README 说明文字）。
- **Step 2:** 更新 `docs/architecture-p1.md`：结构描述改为最终形态（domains 全量落地、兼容壳已拆、services/ 仅剩横切与真实现、api/v1 直连 domains）。
- **Step 3:** 更新 `backend/app/domains/README.md`「兼容」一节：注明迁移期结束、旧路径已拆除。
- **Step 4:** 全量回归 + 全量 import 冒烟：

```bash
cd backend && uv run pytest -q --tb=short
cd backend && uv run python -c "import app.main"
```

- **Step 5: Commit** `refactor(backend): 拆除全部兼容壳并更新架构文档`

### Task 8: 终审 + finishing

- 构建全分支 diff（Base..HEAD），Reviewer 核验：无旧路径残留、无双路径实现、约束零违反、全量测试绿。
- ledger 收尾、fast-forward 合并 main。

---

## Spec coverage

| Phase 6 目标 | Tasks |
|--------------|-------|
| 拆除兼容壳 | 2–6 |
| 域内双路径收口 | 1 |
| api/v1 直连 domains | 2–6（随域）、7（扫尾） |
| 更新 architecture-p1.md | 7 |
| 全量回归 | 每 task 均含 |

## Out of scope

- ops/worker 拓扑重写（`services/ops`、`worker/*`、`services/ai`、`services/team` 等真实现不迁域）
- `models` 整理
- 统一日志 / 请求上下文中间件
- 改前端 / 算法重写
- 新域拆分（`services/strategy`、`quote_collect` 等后续可另开计划）

# Web 日 K 补全 + 内嵌调度 Implementation Plan

> **For agentic workers:** 按任务顺序实现。Commit 仅在用户明确要求时执行。

**Goal:** Ops 可开关/手动/定时跑 `fill_watchlist_bars` 与 `batch_fill_stale`；Tushare daily → `dbbardata`。

**Architecture:** `bar_download` 原语 + `ops_bars_fill` 两 job；`bars_scheduler` 仅调度二者；Ops UI 按钮与文案。

**Tech Stack:** FastAPI lifespan、APScheduler、SQLAlchemy、Tushare HTTP、Vue OpsView。

**Spec:** `docs/superpowers/specs/2026-08-06-bars-fill-scheduler-design.md`

## Global Constraints

- 只改 zak2；无 vnpy；无全市场首下；调度仅两日 K job
- 无 token 明确失败；单票失败不中断整批
- `BARS_SCHEDULER_ENABLED` 可关；`BARS_FILL_MAX_SYMBOLS` 默认 500
- 不做选主 / 改 cron UI

## File map

| 文件 | 职责 |
|------|------|
| `backend/app/services/bar_download.py` | daily 拉取 + upsert + overview 刷新 |
| `backend/app/services/ops_bars_fill.py` | fill_watchlist_bars / batch_fill_stale |
| `backend/app/services/bars_scheduler.py` | APScheduler 启停与互斥 |
| `backend/app/main.py` | lifespan 挂调度 |
| `backend/app/core/settings.py` | 相关 env |
| `ops_catalog` / `ops.py` | 注册可跑 |
| `frontend/src/views/OpsView.vue` + `api/ops.ts` | UI |
| `docs/gap-vs-desktop.md` / `smoke-checklist.md` | 文档 |

---

### Task 1: bar_download + 单测

- [ ] `parse_symbol_to_sse`：`SHSE.600519` / `600519.SSE` → `(symbol, exchange, ts_code)`
- [ ] `download_daily_bars(db, *, symbol, exchange, start, end) -> int`
- [ ] upsert `dbbardata`；刷新 `dbbaroverview`
- [ ] `list_stale_overviews(db, as_of, *, limit)` / `is_stale`
- [ ] pytest mock `ts.query`

### Task 2: 两 job + Ops 注册

- [ ] `fill_watchlist_bars(db)` / `batch_fill_stale(db)`
- [ ] RUNNABLE + _RUNNERS；catalog 测试
- [ ] save_job_run_meta

### Task 3: bars_scheduler

- [ ] 依赖 `apscheduler`
- [ ] lifespan start/stop；enabled 检查；同 job 锁；全市场跑时跳过自选
- [ ] 单测 mock scheduler 触发逻辑

### Task 4: Ops UI + 文档 + 全量验收

- [ ] 按钮 + 文案；overview 不再写「请用 zak CLI」
- [ ] gap / smoke
- [ ] `uv run pytest -q` + `npm run build`

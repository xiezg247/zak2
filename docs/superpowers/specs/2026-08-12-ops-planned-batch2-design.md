# Ops planned 第二批：moneyflow 薄封装 + 自选财报同步 设计

日期：2026-08-12  
状态：已批准（方案 A：两独立 runner + RUNNABLE；enabled 默认 false）  
范围：仅 zak2；不改 zak / vnpy-*；不实现其余 4 个 planned job

## 背景

首批四 job 已合入。剩余 planned 中本刀升级 **2 个**（用户选数据补齐批次 A）：

1. `prefetch_moneyflow`  
2. `sync_watchlist_financials`  

`prefetch_tushare` 已尽力写入同日 `moneyflow`；本刀将 `prefetch_moneyflow` 做成**薄封装**，仅写 `dataset=moneyflow`，便于 Ops 单独重跑主力资金、不重复拉 `daily_basic`。  
财报表（`financial_reports` / `financial_snapshots` / `financial_sync_meta`）DDL 已存在；缺 runner。为省积分：自选全量、**近 2 年**、仅三表（无 `fina_indicator`）。

## 目标

1. 两 job 升级为 **RUNNABLE**：Ops 可手动执行；`DEFAULT_CRON` 展示，**enabled 默认 false**。  
2. 无 token / 空自选 / 空数据 → `skipped` + `save_job_run_meta`。  
3. moneyflow 可单独预热 PG 因子缓存；自选三表写入并重算 snapshot。

## 非目标

- `prefetch_concept_board`、`warm_watchlist_strategy_cache`、`fill_focus_pool_minute`、`scan_horizon_outlook`  
- `fina_indicator` / express / forecast / `valuation_history`  
- 改 AI `team_prefetch` 读路径（本刀只写库）  
- 改 `prefetch_tushare` 行为；默认启用定时；改 zak / vnpy-*

## 决策摘要

| 项 | 选择 |
|----|------|
| 结构 | 每 job 一服务模块 + `ops_runners` 映射（方案 A） |
| moneyflow | 薄封装，仅 `moneyflow` dataset |
| 财报范围 | 全局自选 DISTINCT；`years=2`；income / balancesheet / cashflow |
| 定时 | 有 DEFAULT_CRON；enabled 默认 false |
| TTL 跳过 | 本刀不做；每跑全量刷新自选 |

---

## 1. Job 行为

### 1.1 `prefetch_moneyflow`

- **源**：最近开市日 `fetch_moneyflow_rows`（复用 `tushare_screener`）。  
- **写**：`app.tushare_factor_cache`  
  - `dataset` = `moneyflow`  
  - `trade_date` = YYYYMMDD  
  - `payload` = JSON 数组  
  - `fetched_at` = ISO  
  - PK `(dataset, trade_date)` → upsert  
- **边界**：无 token / API 失败 / 空行 → skipped，不写脏行。与 `prefetch_tushare` 独立，可重复覆盖同日 moneyflow。  
- **Cron**：`{"hour": 15, "minute": 35, "day_of_week": "mon-fri"}`（略晚于 prefetch_tushare 15:30）

### 1.2 `sync_watchlist_financials`

- **标的**：`app.watchlist` DISTINCT `(symbol, exchange)`（复用 `ops_bars_fill.list_watchlist_symbols` 或等价查询）→ `bar_download.to_ts_code`。  
- **源**：Tushare `income` / `balancesheet` / `cashflow`，`years=2`（`start_date` ≈ 今天往前 2×366 天）。  
- **写**：  
  - `app.financial_reports`：`(ts_code, report_type, end_date)` upsert；`payload` 存行字段 JSON；`period` 由 end_date 推断（Q1/H1/Q3/Annual）。  
  - `app.financial_snapshots`：由本地三表按 `end_date` 重算（对齐 zak `compute_snapshots` 字段映射；无 indicator 时 ROE/毛利率等可为 null；营收/净利 YoY、资产负债、现金流尽量填）。  
  - `app.financial_sync_meta`：按票更新 `last_sync_at` / `latest_end_date` / `periods_count` / `sync_status` / `error_message`。  
- **策略**：每跑全量；单票失败记 failed + meta error，**不阻断**整批；票间 sleep ≈ 0.35s 控频。  
- **空自选 / 无 token** → skipped。  
- **成功语义**：至少 1 票成功 → `success=True`；全部失败（有自选但 ok=0）→ `success=False`；message 含 ok/fail 计数。  
- **Cron**：`{"hour": 9, "minute": 0, "day_of_week": "mon"}`

返回值形态：`{success, skipped?, message, ...}` + `save_job_run_meta`。

---

## 2. 模块与注册

| 路径 | 职责 |
|------|------|
| `backend/app/services/ops_prefetch_moneyflow.py` | prefetch_moneyflow |
| `backend/app/services/ops_sync_watchlist_financials.py` | sync_watchlist_financials + snapshot 纯函数 |
| `ops_catalog.py` | 加入 `RUNNABLE_JOB_IDS`；描述微调 |
| `ops_runners.py` | 映射 |
| `scheduler_defaults.py` | DEFAULT_CRON |
| `tests/test_ops_prefetch_moneyflow.py` | mock 成功 / 无 token |
| `tests/test_ops_sync_watchlist_financials.py` | 空自选 skipped + 成功路径 |
| `tests/test_ops_job_kind.py` / guards 等 | planned 夹具改用仍 planned 的 id（如 `prefetch_concept_board`） |
| `docs/product-roadmap.md` / `docs/smoke-checklist.md` | 文档 |

可读 zak 财报逻辑作字段映射参考，**禁止** import vnpy / zak 包。

---

## 3. 验收

1. 两 job `job_kind_for(...) == "runnable"`；RUNNERS 覆盖；DEFAULT_CRON 有键。  
2. mock 单测：moneyflow 写入路径 + 无 token；财报空自选 + 至少一条成功 upsert。  
3. `./scripts/check.sh` 通过。  
4. 可选手动：Ops 执行后 `tushare_factor_cache` / 财报表行数增加。

## 明确不做（复述）

其余 4 planned；`fina_indicator`；改 team 读路径；双写桌面；下单；自动默认启用定时。

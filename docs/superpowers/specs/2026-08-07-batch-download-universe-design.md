# 全市场日 K 首下（Web 可跑）设计

日期：2026-08-07  
状态：已批准（方案 1：扩展 ops_bars_fill + bar_download）  
范围：仅 zak2；不改 zak / vnpy-*；不实现 sync_universe

## 目标

Ops 可手动/定时执行 `batch_download_universe`：按 `app.universe` 为缺 overview 或起点晚于统一起点的标的，从统一起点下载日 K 写入 `dbbardata` / `dbbaroverview`。

## 非目标

- `sync_universe`（列表仍靠桌面或已有表）
- Ops 改 `download_start` UI
- 桌面 no-data 永久跳过 meta、多线程并发
- 分 K / TickFlow / 下单
- 改 zak

## 数据与筛选

**池：** `SELECT symbol, exchange FROM app.universe ORDER BY exchange, symbol`  
空 → `success=False`，提示先同步 A 股列表。

**统一起点：** env `BARS_UNIVERSE_START`，默认 `2020-01-01`；解析失败回退默认。

**纳入目标：**
1. 无 `dbbaroverview`（`interval='d'`）
2. 或 overview.`start` 日期 > 统一起点

**下载区间：** `[unified_start, as_of_trade_date]`；复用 `download_daily_bars`。

**限流：** 单次 `BARS_FILL_MAX_SYMBOLS`（默认 500）；`BARS_FILL_SLEEP_SEC`；串行。

## Job 行为

- job_id：`batch_download_universe`（catalog 已有占位）
- 无 token → 与现有 fill 相同失败结构
- 返回：`success, message, attempted, success_count, failed, bars_added, up_to_date, as_of`；可选 `skipped_covered`
- `save_job_run_meta`
- 写入 `RUNNABLE_JOB_IDS` + `RUNNERS`
- 默认 cron：约 `16:20` mon-fri（对齐桌面；写入 `scheduler_defaults`）

## 互斥

进程内：`batch_download_universe`、`fill_watchlist_bars`、`batch_fill_stale` 三者互斥（任一在跑则跳过另两个触发）。仍用 Redis job 锁。

## 前端（Ops）

- 日 K overview 文案：可补全自选 / 过期 / **全市场首下**（需 universe + token）；可注明起点 env
- 快捷按钮：「全市场日 K 首下」→ `runJob('batch_download_universe', true)`
- 任务表随 RUNNABLE 自动可开关/立即跑

## 测试

- 空 universe → 失败文案
- 筛选：无 overview / start 过晚纳入；已覆盖不纳入
- max 截断；mock 下载不打真网
- 互斥逻辑单测（可扩 embedded_scheduler）

## 文档

- gap：日 K Web 补全 → 含全市场首下（薄：单次上限、依赖已有 universe）
- smoke：Ops 可提交全市场日 K；无列表/无 token 有明确失败

## 验收

1. Ops 可手动跑 `batch_download_universe`  
2. 无列表 / 无 token 有中文说明  
3. mock 下目标计数与截断正确  
4. pytest + `npm run build` 绿  

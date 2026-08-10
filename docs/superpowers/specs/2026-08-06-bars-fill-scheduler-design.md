# Web 日 K 补全 + 内嵌调度（薄）设计

日期：2026-08-06  
状态：已批准（方案 1）  
范围：仅 zak2；不改 zak / vnpy-*

## 目标

Ops 可开关并手动/定时执行两类日 K 补全：

1. `fill_watchlist_bars` — 自选（及可选持仓组）过期/缺失日 K  
2. `batch_fill_stale` — 全市场 overview 过期日 K（带单次上限）

内嵌 APScheduler **仅**调度上述两个 job。

## 非目标

- 全市场首下 `batch_download_universe`
- 分 K / TickFlow
- 多实例选主
- 调度其它非日 K 可跑 job
- Web 修改 cron UI（只读展示现有 cron 字段）

## 数据与原语

**源：** Tushare `daily`（需 `TUSHARE_TOKEN`）。  

**写：** `public.dbbardata`，`interval='d'`；exchange/symbol 与现有 VeighNa 约定一致（如 `SSE`/`SZSE` + 代码）。  

**Overview：** 更新 `public.dbbaroverview` 该标的 start/end/count，供 Ops overview 与过期判定。

**原语：** `download_daily_bars(db, symbol_key, start, end) -> int`  
- 拉取 → 按 (symbol, exchange, datetime, interval) upsert  
- 刷新 overview 行  

**过期：** overview.`end` 日期 &lt; 最近开市日（`trade_calendar`）→ stale；无 overview → 待补（自选路径）。

## Job 行为

### `fill_watchlist_bars`

- 池：Web 自选 vt/tf 符号（可含持仓组若已有 API/表）  
- 过滤 stale 或无 overview  
- 限并发 + 简单限流  
- 返回 `attempted / success / failed / bars_added`  
- 无 token → `success=False` + 中文说明  

### `batch_fill_stale`

- 池：`dbbaroverview` 中 interval=d 且 stale  
- env `BARS_FILL_MAX_SYMBOLS`（默认如 500）截断单次  
- 同上限流与返回结构  

## Ops / 可跑注册

- 二者加入 `RUNNABLE_JOB_IDS` 与 `_RUNNERS`  
- 手动：现有异步 `POST /api/v1/ops/scheduler/jobs/{id}/run`  
- 开关：现有 `patch_job_enabled` → `system.scheduler_config`  
- 默认 cron（写入 defaults / 文档）：自选约 18:00，全市场约 18:30（与桌面盘后习惯接近；可从 config 读 hour/minute）

## 内嵌调度

- 依赖：`apscheduler`  
- FastAPI `lifespan` 启动 `BackgroundScheduler`  
- **仅**注册上述两 job  
- 触发前检查 `enabled`；进程内互斥（同 job 不并行）  
- 两 job 互斥策略：全市场运行中则跳过自选（或串行队列，实现时择一写死并测）  
- env `BARS_SCHEDULER_ENABLED`（默认 true；测试可关）  
- 多 API 副本可能双跑：文档注明单实例或关多余开关  

## 前端（Ops）

- 日 K overview 文案：改为 Web 可补全（去掉「请用 zak CLI」）  
- 快捷按钮：补全自选日 K / 补全过期日 K  
- 任务表：两行开关 + 立即跑（异步）+ 上次运行 meta  

## 错误处理

| 情况 | 行为 |
|------|------|
| 无 token | job 失败，明确文案 |
| 单票 Tushare 失败 | 记入 failed，继续下一批 |
| overview/表异常 | job 失败或该票失败，不 500 整个 API 进程 |

## 测试

- mock Tushare 的 download upsert  
- watchlist / stale 池与 `max_symbols`  
- enabled=false 不调度；同 job 互斥  
- 不打真网  

## 文档

更新 `docs/gap-vs-desktop.md`、`docs/smoke-checklist.md`。

## 验收

1. Ops 可开关两 job，config 持久化  
2. 有 token（或 mock）时手动跑自选补全能写库  
3. 调度开启且 enabled 时到点触发（测试可用注入/短周期验证）  
4. pytest + 前端 build 通过  

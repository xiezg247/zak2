# Web 同步 A 股列表（sync_universe）设计

日期：2026-08-07  
状态：已批准（方案 1：Tushare stock_basic → 全量替换 app.universe）  
范围：仅 zak2；不改 zak / vnpy-*；不接 TickFlow

## 目标

Ops 可手动/定时执行 `sync_universe`：用 Tushare `stock_basic`（上市中）全量刷新 `app.universe`，供全市场日 K 首下等 job 自给列表。

## 非目标

- TickFlow 同步
- `sync_stock_industry` / 行业映射
- 改日 K 首下筛选逻辑（仅解除对桌面列表的硬依赖）
- 改 zak

## Job 行为

**源：** Tushare `stock_basic`，`list_status=L`，字段至少 `ts_code,name`。

**映射：**
- `600519.SH` → `symbol=600519`, `exchange=SSE`
- `.SZ` → `SZSE`；`.BJ` → `BSE`
- 未知后缀 → 跳过，计入 `skipped`

**写库（同一事务）：**
1. `DELETE FROM app.universe`
2. 分批 INSERT（chunk≈500）`(symbol, exchange, name)`
3. 写 `app.meta` 键 `universe_synced_at` = ISO 时间（与桌面同键，便于新鲜度）

**返回：** `success, message, count, skipped`  
- 无 token / 拉取失败 / 映射后 0 条 → `success=False` + 中文说明  
- `save_job_run_meta`

**注册：**
- `RUNNABLE_JOB_IDS` + `RUNNERS`
- 默认 cron：周一 `08:00`（对齐桌面）
- catalog 描述改为：`Tushare stock_basic → app.universe（Web 可跑）`

## Ops UI

- 日 K 区文案：全市场首下前可先「同步 A 股列表」；需 `TUSHARE_TOKEN`
- 快捷按钮：「同步 A 股列表」→ `runJob('sync_universe', true)`（与日 K 按钮同区或紧邻）
- `runJob` 分支纳入异步 `opsApi.runJob`（同其它 bars job）
- 任务表随 RUNNABLE 可开关/立即跑

## 测试

- 映射：SH/SZ/BJ；未知后缀跳过
- mock Tushare：空结果失败；有数据则 DELETE+INSERT 调用正确、返回 count
- 无 token 失败
- catalog / defaults 含 `sync_universe`
- 不打真网

## 文档

- gap：运维/日 K 依赖 — Web 可 sync_universe（Tushare，非 TickFlow）
- smoke：Ops 可提交同步 A 股列表；无 token / 空结果有明确失败

## 验收

1. Ops 可手动跑 `sync_universe` 并刷新 `app.universe`  
2. 无 token / 空列表有中文说明  
3. 之后可再跑全市场日 K 首下（有列表时）  
4. pytest + `npm run build` 绿  

# Web 同步行业映射（sync_stock_industry）设计

日期：2026-08-10  
状态：已批准（方案 1：新建 `app.stock_industry` + 对齐 sync_universe）  
范围：仅 zak2；不改 zak；本刀只同步，不改选股/行情读路径

## 目标

Ops 可手动/定时执行 `sync_stock_industry`：Tushare 申万 2021 L2（失败回退 `stock_basic.industry`）全量刷新 `app.stock_industry`。

## 非目标

- 写入桌面 `tushare_factor_cache`
- 硬过滤 / quotes / engine 读该表
- 改 zak / vnpy-*
- 下单

## 表

`app.stock_industry`（`CREATE TABLE IF NOT EXISTS`）：

| 列 | 说明 |
|----|------|
| `symbol` | 代码 |
| `exchange` | `SSE` / `SZSE` / `BSE` |
| `industry` | L2 名或 stock_basic 行业 |
| `industry_l1` | L1 名，可空 |
| `source` | `sw2021_l2` \| `stock_basic` |
| `updated_at` | ISO 文本 |

PK：`(symbol, exchange)`

## Job

`ops_sync_stock_industry.sync_stock_industry(db) -> dict`

1. 无 token → `success=False` + 中文  
2. 优先 `index_member_all`（`is_new=Y`，字段含 `ts_code,l1_name,l2_name,out_date`）：无 `out_date` 为活跃；`industry=l2`（空则 l1）；映射 `ts_code`→`(symbol,exchange)`（同 universe：SH→SSE 等）  
3. 申万 0 条有效 → 回退 `stock_basic`（`list_status=L`，`ts_code,industry`），`source=stock_basic`，`industry_l1=""`  
4. 仍 0 条 → 失败  
5. 事务内：`DELETE FROM app.stock_industry` + chunk INSERT（≈500）  
6. `app.meta` 键 `stock_industry_synced_at`；`save_job_run_meta`  
7. 返回：`success, message, count, skipped, source`

## 注册

- `RUNNABLE_JOB_IDS` + `RUNNERS["sync_stock_industry"]`  
- 默认 cron：周一 `08:15`  
- catalog 描述：`Tushare 申万 L2 → app.stock_industry（Web 可跑；失败回退 stock_basic）`

## Ops UI

- 快捷按钮「同步行业映射」→ `runJob('sync_stock_industry', true)`（与 sync_universe 同异步分支）  
- 日 K/同步区旁；文案注明需 token、写入 `app.stock_industry`  
- 任务表随 RUNNABLE 可开关/立即跑

## 测试

- 映射 SH/SZ/BJ；未知后缀 skipped  
- mock 申万有数据 → DELETE+INSERT、`source=sw2021_l2`  
- mock 申万空 → 回退 stock_basic  
- 无 token / 空结果失败  
- catalog / defaults / runners 含本 job  
- 不打真网  

## 文档

- gap：运维 Web 可跑行业映射；建议下一刀另定  
- smoke：Ops 可提交；无 token / 空结果失败文案明确  

## 验收

1. Ops 手动跑通并刷新表  
2. 无 token / 空列表中文失败  
3. pytest + `npm run build` 绿  

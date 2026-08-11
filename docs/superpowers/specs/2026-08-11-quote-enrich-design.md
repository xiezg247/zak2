# 行情因子 Enrich（enrich_market_quotes）设计

日期：2026-08-11  
状态：已批准（方案 1：独立 RUNNABLE job + 合并写回 Redis）  
范围：仅 zak2；不改 zak / vnpy-*；不改 quote-collector 主循环

## 背景

TickFlow collector 已写入价量与部分 `turnover_rate`，但 `volume_ratio` / `net_mf_amount` / 市值等常为 0；稀疏榜几乎为空。选股侧已有 Tushare `daily_basic` / `moneyflow` 拉取。Ops catalog 中 `enrich_market_quotes` 仅为 planned 占位。

产品路线候选：行情 enrich 因子。本刀先落地；AI 只读工具另立项。

## 目标

1. 将 `enrich_market_quotes` 升级为 **RUNNABLE** job（Ops 手动执行；默认定时关闭）。  
2. 用 Tushare 因子 **补丁** 已有 `zak2:quote:{TF}` HASH（不覆盖价量 OHLC）。  
3. 刷新相关排行榜并 `INCR seq` + `PUBLISH` notify，前端可感知。

## 非目标

- 不把 enrich 挂进 collector 每轮循环  
- 不建侧车 `zak2:factor:*` 键  
- 不实现 `prefetch_tushare` / `prefetch_moneyflow`  
- 不改 AI 工具  
- 不 import vnpy_*  

## 决策摘要

| 项 | 选择 |
|----|------|
| 进程 | API/Ops runner（与其它 sync job 相同） |
| 数据源 | `daily_basic` + `moneyflow` |
| 定时 | `DEFAULT_CRON` 可给 15:20 mon-fri；**enabled 默认 false** |
| 写策略 | 仅更新已存在 quote 键的因子字段 |

---

## 1. 数据流与字段

```text
TUSHARE_TOKEN 缺失 → skipped
解析最近开市日 trade_date（复用 trade_calendar / lookback）
        │
        ├─ daily_basic → turnover_rate, volume_ratio, total_mv, circ_mv
        └─ moneyflow  → net_mf_amount（0 时可大单净额回退，对齐 tushare_screener）
        │
ts_code → TF 符号（SHSE./SZSE./BJSE.）
        │
仅 HSET 已存在的 zak2:quote:{TF} 因子字段
        │
重建榜：turnover_rate；稀疏 volume_ratio / net_mf_amount
（本刀可不重建 change_pct 等无关榜）
        │
INCR zak2:meta:seq → PUBLISH zak2:notify:quotes
```

### HASH 补丁字段

| 来源 | field |
|------|-------|
| daily_basic | `turnover_rate`, `volume_ratio`, `total_mv`, `circ_mv` |
| moneyflow | `net_mf_amount` |

不改：价量 OHLC、`limit_times`、`industry`、`name` 等。

### 边界

- Redis 无 quote 键 → skip，提示先跑 collector  
- 单源失败：另一源仍可写；message 注明  
- 空补丁集合：不 incr / 不 publish  

---

## 2. 组件与注册

### 服务

建议：`backend/app/services/ops_enrich_quotes.py`（或 `quote_enrich.py` + ops 薄封装）

```text
enrich_market_quotes(db: Session) -> dict
# keys: success, skipped, message, extra(optional: trade_date, updated, ranks…)
```

复用：

- `tushare_screener.fetch_daily_basic_rows` / `fetch_moneyflow_rows`（或等价 `_fetch_with_lookback`）  
- `app.core.redis_keys` 键常量  
- 符号：`to_tf_symbol` / 现有 ts_code 解析（与 `ops_sync_universe.parse_ts_code` 等对齐）

写 Redis：可用独立 helper（如 `apply_factor_patches(client, patches) -> int`），**避免**调用 `RedisQuoteWriter.write_quotes` 全量覆盖价量。

榜重建：对涉及 field `DELETE` + `ZADD`（成员来自「被补丁且仍存在的 quote」或扫 HASH；实现选成本更低且正确的一种，单测锁语义）。

### Ops 接线

| 文件 | 改动 |
|------|------|
| `ops_catalog.RUNNABLE_JOB_IDS` | 加入 `enrich_market_quotes` |
| `ops_catalog` 描述 | Tushare → Redis 因子 |
| `ops_runners.RUNNERS` | 注册 runner |
| `scheduler_defaults.DEFAULT_CRON` | 可选 `15:20 mon-fri` |
| 测试 | catalog ⊆ runners；enrich 单测（mock Redis/Tushare） |

`job_kind` 自动变为 `runnable`（已有映射）。

### 返回语义

| 情况 | skipped | success | message |
|------|---------|---------|---------|
| 无 token | true | — | 未配置 TUSHARE_TOKEN |
| Redis 不可用/无行情 | true | — | 请先 collector |
| 双源无数据 | true | — | 无 Tushare 数据 |
| 部分成功 | false | true | 更新 N；注明失败源 |
| 全成功 | false | true | 更新 N；trade_date |

`save_job_run_meta` 与其它 sync 一致。不与 bars 三件套互斥。

---

## 3. 测试与文档

### 测试

- 无 token → skipped  
- mock basic+moneyflow → HSET 字段与稀疏/换手榜调用  
- 无已有 quote key → 不写、不 publish  
- `RUNNABLE` 含该 id 且 `RUNNERS` 对齐  

### 文档

- `docs/product-roadmap.md`：候选 enrich 标进行中/完成并链本 spec  
- `docs/smoke-checklist.md`：Ops 手动 enrich 一条（需 token + 有行情）  
- 可选：quote-collector design 非目标中「第二刀 enrich」改为已有独立 spec  

---

## 验收

1. Ops 任务为可跑；默认开关关，手动可执行  
2. 无 token / 无行情 → skip  
3. 有条件时 HASH 因子非空，稀疏榜在有效值时有成员  
4. seq + notify 前进  
5. pytest 绿  

## 风险

| 风险 | 对策 |
|------|------|
| Tushare 积分/限流 | 默认定时关；失败可 skip/部分成功 |
| 全量扫 Redis 成本 | 仅对 patch 命中的 TF 更新榜成员；或有界 SCAN |
| 与 collector 并发写 | 补丁字段与价量分离；极端下以最后写入为准，可接受 |

## 实现计划

实现计划：`docs/superpowers/plans/2026-08-11-quote-enrich.md`

# Ops planned 首批升级：停牌 / 披露 / 因子缓存 / 雷达预热 设计

日期：2026-08-11  
状态：已批准（方案 A：四独立 runner + RUNNABLE；enabled 默认 false）  
范围：仅 zak2；不改 zak / vnpy-*；不实现其余 6 个 planned job

## 背景

Ops catalog 中 10 个 job 仍为 `planned` 占位。本刀升级其中 **4 个**（用户选批次 B）：

1. `sync_suspend_daily`  
2. `sync_disclosure_calendar`  
3. `prefetch_tushare`  
4. `warm_radar_card_snapshots`  

表结构已存在（import 或 DDL）；缺 runner / RUNNABLE / cron。  
`enrich_market_quotes` 已覆盖 Redis 路径 moneyflow/daily_basic；本刀 `prefetch_tushare` 写入 **PG** `tushare_factor_cache`，与 enrich 互补。

## 目标

1. 四 job 升级为 **RUNNABLE**：Ops 可手动执行；`DEFAULT_CRON` 展示，**enabled 默认 false**。  
2. 无 token / 空数据 → `skipped` + `save_job_run_meta`（对齐 enrich）。  
3. 硬过滤停牌、披露查阅、本地因子缓存、雷达首屏延迟均可受益。

## 非目标

- `prefetch_moneyflow`、`prefetch_concept_board`、`sync_watchlist_financials`、`warm_watchlist_strategy_cache`、`fill_focus_pool_minute`、`scan_horizon_outlook`  
- 改 `hard_filters` 行为（表有数据后自然可用；本刀可不改选股逻辑）  
- 改 enrich / quote-collector  
- 分钟 K、策略引擎、LLM 展望  

## 决策摘要

| 项 | 选择 |
|----|------|
| 结构 | 每 job 一服务模块 + `ops_runners` 映射 |
| 定时 | 有 DEFAULT_CRON；enabled 默认 false |
| 因子预拉 | 至少 `daily_basic`；可选同日 `moneyflow` 另一 dataset 行 |

---

## 1. Job 行为

### 1.1 `sync_suspend_daily`

- **源**：Tushare `suspend_d`，`suspend_type='S'`，`trade_date` = 最近开市日；失败可 lookback 若干日。  
- **写**：`app.symbol_suspend_days`（symbol, exchange, cal_date, suspend_type）  
  - `ts_code` → TF/symbol+exchange（复用 `ts_code_to_tf` / 拆分）  
  - `cal_date` ← `trade_date`（YYYYMMDD 或存库约定与现表一致：现为 text）  
- **策略**：按日 upsert（先删该 `cal_date` 再插，或 ON CONFLICT）；message 含写入条数。  
- **Cron**：`{"hour": 17, "minute": 40, "day_of_week": "mon-fri"}`

### 1.2 `sync_disclosure_calendar`

- **源**：Tushare `disclosure_date`，按报告期 `end_date`（最近季末，如 3/6/9/12 月末 YYYYMMDD）。  
- **写**：`app.disclosure_calendar`（ts_code, end_date, pre_date, ann_date, actual_date, fetched_at）  
  - PK 以现表为准（若无 PK，用 delete+insert by end_date 或 upsert 组合键）。  
- **限量**：接口单次最大约 6000；一季通常够用。积分不足 → skipped。  
- **Cron**：`{"hour": 8, "minute": 30, "day_of_week": "mon"}`

### 1.3 `prefetch_tushare`

- **源**：最近开市日 `daily_basic`（必选）；可选同日 `moneyflow`。  
- **写**：`app.tushare_factor_cache`  
  - `dataset` = `daily_basic` / `moneyflow`  
  - `trade_date` = YYYYMMDD  
  - `payload` = JSON 数组（行列表或精简字段）  
  - `fetched_at` = ISO 时间  
  - PK `(dataset, trade_date)` → upsert  
- **边界**：与 enrich 独立；enrich 仍写 Redis。无 token → skipped。  
- **Cron**：`{"hour": 15, "minute": 30, "day_of_week": "mon-fri"}`

### 1.4 `warm_radar_card_snapshots`

- **源**：现有合成函数（`radar._synth_leader_pick` / `_synth_limit_ladder` / `_synth_sector_hot` / `_synth_change_top`），建议抽公共 `build_synthesized_cards(db) -> list[RadarCardOut]` 供 list 与 warm 共用，避免复制。  
- **写**：`cache.radar_card_snapshot`（card_id, variant_key='' , payload_json, computed_at）upsert。  
- **payload_json**：含 title/subtitle/rows/empty_message（与 `_from_cache` 读取一致）。  
- **Cron**：可用多 hour，例如 `{"hours": [9, 10, 14], "minute": 20, "day_of_week": "mon-fri"}`（与草案 9:20/10:05/14:05 等价即可，实现取整点分钟一致即可）。

---

## 2. 模块与注册

| 路径 | 职责 |
|------|------|
| `backend/app/services/ops_sync_suspend.py` | sync_suspend_daily |
| `backend/app/services/ops_sync_disclosure.py` | sync_disclosure_calendar |
| `backend/app/services/ops_prefetch_tushare.py` | prefetch_tushare |
| `backend/app/services/ops_warm_radar.py` | warm_radar_card_snapshots |
| `backend/app/services/radar.py` | 可选抽取 `build_synthesized_cards` |
| `ops_catalog.py` | 加入 `RUNNABLE_JOB_IDS`；描述可微调 |
| `ops_runners.py` | 映射 |
| `scheduler_defaults.py` | DEFAULT_CRON |
| `tests/test_ops_sync_suspend.py` 等 | mock Tushare / DB |
| `tests/test_ops_job_kind.py` / catalog | runnable 断言；原 planned 夹具改用仍 planned 的 id |
| `docs/product-roadmap.md` / `smoke-checklist.md` | 文档 |

返回值形态对齐其它 sync：`{success, skipped?, message, ...}` + `save_job_run_meta`。

---

## 3. 验收

1. 四 job `job_kind_for(...) == "runnable"`；RUNNERS 覆盖；DEFAULT_CRON 有键。  
2. mock 单测：成功写入路径 + 无 token skipped。  
3. `./scripts/check.sh` 通过。  
4. 可选手动：Ops 执行后表行数增加 / 雷达读 cache。

## 明确不做（复述）

其余 6 planned；双写桌面；下单；自动默认启用定时。

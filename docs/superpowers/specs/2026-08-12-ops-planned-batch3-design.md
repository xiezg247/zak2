# Ops planned 第三批：策略预热 / 雷达展望（诚实 skipped 壳）设计

日期：2026-08-12  
状态：已批准（方案 A：两独立 skipped 壳 + RUNNABLE；enabled 默认 false）  
范围：仅 zak2；不改 zak / vnpy-*；不实现其余 2 个 planned（concept / 分钟线）

## 背景

第二批后仍剩 4 个 planned。本刀升级盘后体验两项（用户选批次 A、深度 1、方案 A）：

1. `warm_watchlist_strategy_cache`  
2. `scan_horizon_outlook`  

zak2 `strategy_board` 为只读 cache（不跑策略）；无 horizon/predict 扫描管线。表结构已存在（`watchlist_signal_cache` / `watchlist_position_cache` / `radar_horizon_cache` / `radar_predict_cache`），但本刀**不写入有效计算结果**。

## 目标

1. 两 job 升级为 **RUNNABLE**：Ops 可手动执行；`DEFAULT_CRON` 展示，**enabled 默认 false**。  
2. **诚实 skipped 壳**：明确 message；`save_job_run_meta(last_success=False)`；不写 cache。  
3. JobSpec / roadmap / smoke 标明缺口，便于后续接策略引擎与展望管线。

## 非目标

- 策略信号计算 / 移植 zak `prewarm_watchlist_strategy`  
- horizon/predict 全市场扫描  
- Redis→PG 桥接  
- `prefetch_concept_board`、`fill_focus_pool_minute`  
- 默认启用定时；改 zak / vnpy-*

## 决策摘要

| 项 | 选择 |
|----|------|
| 结构 | 每 job 一服务模块 + `ops_runners` 映射 |
| 行为 | 恒 skipped（本刀无真跑分支） |
| 定时 | 有 DEFAULT_CRON；enabled 默认 false |

---

## 1. Job 行为

### 1.1 `warm_watchlist_strategy_cache`

- **行为**：不计算、不写 `cache.watchlist_signal_cache` / `watchlist_position_cache`。  
- **返回**：`{success: False, skipped: True, message: "zak2 尚未接入策略引擎，无法预热 watchlist_signal/position cache"}`（文案可微调用语，语义不变）。  
- **meta**：`save_job_run_meta(..., last_success=False)`。  
- **Cron**：`{"hour": 18, "minute": 45, "day_of_week": "mon-fri"}`

### 1.2 `scan_horizon_outlook`

- **行为**：不扫描、不写 `cache.radar_horizon_cache` / `radar_predict_cache`。  
- **返回**：`{success: False, skipped: True, message: "zak2 尚未接入雷达展望扫描管线，无法写入 radar_horizon/predict cache"}`。  
- **meta**：`save_job_run_meta(..., last_success=False)`。  
- **Cron**：`{"hour": 18, "minute": 15, "day_of_week": "mon-fri"}`

---

## 2. 模块与注册

| 路径 | 职责 |
|------|------|
| `backend/app/services/ops_warm_watchlist_strategy.py` | warm skipped 壳 |
| `backend/app/services/ops_scan_horizon_outlook.py` | horizon skipped 壳 |
| `ops_catalog.py` | RUNNABLE + JobSpec 描述注明占位 skipped |
| `ops_runners.py` | 映射 |
| `scheduler_defaults.py` | DEFAULT_CRON |
| `tests/test_ops_warm_watchlist_strategy.py` | skipped + meta |
| `tests/test_ops_scan_horizon_outlook.py` | skipped + meta |
| `tests/test_ops_job_kind.py` / guards | planned 夹具继续用 `prefetch_concept_board`（或仍 planned 的 `fill_focus_pool_minute`） |
| `docs/product-roadmap.md` / `smoke-checklist.md` | 文档 |

---

## 3. 验收

1. 两 job `job_kind_for(...) == "runnable"`；RUNNERS 覆盖；DEFAULT_CRON 有键。  
2. 单测：调用后 `skipped is True` 且 `save_job_run_meta` 被调用；无 DB 写 cache 断言（可不 execute 写表）。  
3. `./scripts/check.sh` 通过。  
4. Ops 手动跑可见明确 skipped 文案。

## 明确不做（复述）

策略引擎；horizon 管线；Redis 桥接；concept / 分钟线；双写桌面；下单；自动默认启用定时。

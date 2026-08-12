# Ops 三 skipped job 薄做实设计

日期：2026-08-12  
状态：已批准（方案 A：有副作用 + 诚实边界；不引入 arq/Celery）  
范围：仅 zak2；不改 zak / vnpy-*

## 背景

下列三 job 仍为诚实 skipped 壳（batch3/4）：

1. `warm_watchlist_strategy_cache`
2. `prefetch_concept_board`
3. `fill_focus_pool_minute`

策略看盘只读 Redis/PG cache、无写入引擎；概念资金已由 `sync_sector_flow_daily` 落 `sector_flow_daily`；日 K 可补、**无** 1m 下载管线。本刀以现有能力做「薄做实」，使 Ops 手动跑不再恒 skipped。

## 目标

1. 三 job **不再恒 skipped**；走现有 `ops_runners` + 内嵌 APScheduler。  
2. 各有真实副作用或诚实盘点；无数据时仍 `success=True, skipped=False`（概念无 Tushare token 时除外，见下）。  
3. 更新 catalog 文案、smoke、roadmap（**#27**）；`./scripts/check.sh` 绿。

## 非目标

- 策略引擎真算 / 移植 zak `prewarm_watchlist_strategy`  
- 新建 ths_member「概念成员板」全量管线  
- 真下载 1m 写入 `dbbardata`  
- 引入 arq / Celery 或其它独立 worker 队列  
- 默认启用定时；`needs_user_id`；改 zak / vnpy-*

## 决策摘要

| 项 | 选择 |
|----|------|
| 深度 | 1：薄做实 |
| 方案 | A：有副作用 + 诚实边界 |
| 队列 | 不引入；沿用 APScheduler + RUNNERS |
| 空/无数据 | 策略/1m：success + 计数 0；概念：透传 sector sync（无 token → skipped） |

---

## 1. `warm_watchlist_strategy_cache`

### 1.1 行为

Redis → PG 桥：

1. 确定 `config_key` 集合：至少包含默认 `AshareShortBreakoutStrategy:5:10`；可并入库内 `auth.user_preferences`（namespace=`watchlist`, key=`signal_config`）解析出的键（与 `strategy_board.resolve_config_key` 同规则，无用户则跳过偏好）。  
2. 对每个 `config_key`：  
   - `SCAN` `{KEY_PREFIX}:cache:signal:latest:{ck}:*` → upsert `cache.watchlist_signal_cache`（`vt_symbol`, `config_key`, `bar_as_of`, `payload`, `updated_at`）  
   - `SCAN` `{KEY_PREFIX}:cache:position:latest:{ck}:*` → upsert `cache.watchlist_position_cache`（另含 `position_key`）  
3. payload 存 Redis 原文或规范化 JSON 字符串；`bar_as_of` / `updated_at` 从 envelope 取，缺省用当日（中国时区日期字符串）。

### 1.2 返回 / meta

- 成功：`{success: True, skipped: False, message, written_signals, written_positions}`  
- Redis 不可用或 0 命中：仍 success，written=0，message 说明「无 Redis 信号可桥接」。  
- `save_job_run_meta(..., last_success=True)`（桥接过程异常则 False + message）。

### 1.3 不做

跑策略、伪造买卖点 payload。

---

## 2. `prefetch_concept_board`

### 2.1 行为

调用 `sync_sector_flow_daily(db)`（已含同花顺/东财概念 → `app.sector_flow_daily`），本 job 自行 `save_job_run_meta`。

### 2.2 返回 / meta

| 子结果 | 本 job |
|--------|--------|
| sector sync `skipped`（如无 token） | `success=False, skipped=True`，透传 message |
| sector sync `success` | `success=True, skipped=False`，message 前缀「概念预拉（复用 sector sync）」+ 子摘要 |
| sector sync 失败且非 skipped | `success=False, skipped=False`，透传 message |

### 2.3 不做

ths_member 成员表、内存概念板、独立 Tushare 概念接口（除非已在 sector sync 内）。

---

## 3. `fill_focus_pool_minute`

### 3.1 薄关注池

- 来源：`list_watchlist_symbols(db)` 去重（全站自选）。  
- 上限：500（超出截断并在 message 注明）。

### 3.2 盘点

对池内标的查 `public.dbbaroverview`：

- `with_daily`：`interval='d'` 有 overview 的数量  
- `with_1m`：`interval='1m'` 有 overview 的数量  
- `missing_1m = pool_size - with_1m`（按池内标的计）

**不**下载、**不**写 `dbbardata`。

### 3.3 返回 / meta

```text
{
  success: True,
  skipped: False,
  pool_size, with_daily, with_1m, missing_1m,
  message  # 须含「1m 下载未接入，本跑仅盘点」
}
```

`save_job_run_meta(..., last_success=True)`。

---

## 4. Catalog / 调度

- `ops_catalog.py`：三 job 描述去掉「占位 → skipped」措辞；改为桥接 / 复用 sector / 盘点语义。  
- `DEFAULT_CRON` 与 **enabled 默认 false** 不变。  
- 仍为 `RUNNABLE`；不改 `ops_runners` 映射键名。

---

## 5. 测试

| 文件 | 要点 |
|------|------|
| `test_ops_warm_watchlist_strategy.py` | mock Redis scan → written>0；无 Redis → success、written=0 |
| `test_ops_prefetch_concept_board.py` | mock `sync_sector_flow_daily` 成功 / skipped |
| `test_ops_fill_focus_pool_minute.py` | mock overview → 字段与「未接入」文案 |
| 共通 | 断言 `save_job_run_meta`；成功路径 `last_success=True` |

---

## 6. 文档

- `docs/smoke-checklist.md`：三 job 从「恒 skipped」改为对应薄做实验收条。  
- `docs/product-roadmap.md`：新增 **#27** 完成项，链本 spec。

---

## 7. 验收

1. Ops 手动跑：策略与 1m 非 skipped；概念在有 token 且 sector 可跑时非 skipped。  
2. 策略有 Redis 命中时可在 PG `watchlist_*_cache` 见到行；概念成功路径与 sector sync 一致；1m 返回盘点数字。  
3. smoke / roadmap #27；`./scripts/check.sh` 绿。

## 明确不做（复述）

策略真算；ths_member；1m 下载；arq/Celery；默认启用定时；改 zak / vnpy-*。

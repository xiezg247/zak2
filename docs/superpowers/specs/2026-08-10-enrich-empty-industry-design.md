# 选股补全空行业（读 app.stock_industry）设计

日期：2026-08-10  
状态：已批准（方案 1：共享 enrich，硬过滤前补全）  
范围：仅 zak2；不改 zak；不写 Redis；无硬过滤行业下拉 API

## 目标

条件选股 / 多因子配方 / 雷达龙头在硬过滤前，对 `QuoteRow.industry` 为空的行，用 `app.stock_industry` 补全申万 L2（或 sync 回退写入的 industry）。

## 非目标

- 覆盖已有非空 industry（Redis 优先）  
- Hub 行业勾选列表 API  
- 写回 Redis / 改 sync job  
- `radar_resonance` 路径  
- 改 zak  

## 读侧模块

`backend/app/services/stock_industry.py`（与 `ops_sync_stock_industry` 分离）：

- `load_industry_map(db: Session) -> dict[str, str]`  
  - 键：TickFlow `SHSE.600519`（由 `symbol`+`exchange` 经 `to_tf_symbol`）  
  - 值：`industry` 列  
  - 表空 / 异常 → `{}`（不抛）  
- `enrich_empty_industries(rows: list[QuoteRow], mapping: dict[str, str]) -> int`  
  - 仅 `not (row.industry or "").strip()` 且 `mapping.get(row.symbol)` 命中时赋值  
  - 返回补全条数  

可选薄封装：`enrich_rows_from_db(db, rows) -> int` — `db is None` 则 0；否则 load + enrich。

## 挂载点（有 db 时，`apply_hard_filters` 之前）

1. `engine.run_condition_screen` — 各分支在硬过滤前（含 Tushare 行与 Redis 池）  
2. `engine.run_recipe_screen` — 普通配方在硬过滤前  
3. `leader_screen.run_leader_screen` — `build_candidate_pool` 后、硬过滤前  

`db is None` 跳过。

## 测试

- enrich：空补全 / 非空保留 / 未命中不变  
- load：mock 行 → tf 键  
- engine 或 leader：mock map，过滤前行业已补  
- 不打真网  

## 文档

- gap：选股/龙头可补空行业；仍无行业下拉 API  
- smoke：先 Ops 同步行业映射；缺 Redis 行业时配方/龙头结果可见行业名  

## 验收

1. 表有数据且 Redis 行业空 → 结果带 industry  
2. Redis 已有 → 不覆盖  
3. pytest + `npm run build` 绿  

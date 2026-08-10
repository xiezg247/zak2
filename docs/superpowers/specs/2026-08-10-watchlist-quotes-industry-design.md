# 自选/看盘 quotes enrich 读 app.stock_industry 设计

日期：2026-08-10  
状态：已批准（方案 A：复用 enrich_rows_from_db）  
范围：仅 zak2；不改 zak；不写 Redis；不含策略板

## 目标

自选列表（`GET /watchlist` enrich）与看盘 `GET /quotes` 返回 `industry`；Redis 非空优先，空则用 `app.stock_industry` 补全；Watchlist 表展示「行业」列。

## 非目标

- 覆盖已有非空 industry（Redis 优先）
- 策略看盘 / strategy-board 行带行业
- 写回 Redis / 改 sync job
- 按 symbol 增量 load（本刀沿用全表 `load_industry_map`）
- 改 zak

## 数据流

1. Redis `get_quotes` → 行情行（可含空 `industry`）
2. 构造成 `QuoteRow` 列表 → `enrich_rows_from_db(db, rows)`（仅补空）
3. 写入 `WatchlistItemOut.industry` / `QuoteOut.industry`（默认 `""`）
4. 前端类型加字段；自选表「名称」后加「行业」列（空显示 `—`）

`enrich=false`（`with_quotes=False`）：不拉行情、不查行业，`industry=""`。

## Schema / API

| 项 | 说明 |
|----|------|
| `WatchlistItemOut` | 增加 `industry: str = ""` |
| `QuoteOut` | 增加 `industry: str = ""` |
| `_enrich` | `with_quotes=True` 时注入 `db`，enrich 后写字段 |
| `GET /quotes` | 增加 `db: Session`；同样 Redis → enrich → 出参 |

复用 `app.services.stock_industry.enrich_rows_from_db`；不新增 map API。

## 前端

- `WatchlistItem`（及 Quote 相关类型若有）加 `industry?: string`
- `WatchlistView` 表格：名称列后「行业」；可选详情头一行行业
- 策略板 UI 不动
- WS 仅触发 list 刷新，行业随 `_enrich` 一并更新

## 测试

- `_enrich`：Redis 空 + map 命中 → 有值；非空不覆盖；`with_quotes=False` → `""`
- `/quotes`：同类（mock store + map）
- 不打真网

## 文档

- `docs/gap-vs-desktop.md`：自选 enrich 行标为已接 `stock_industry`
- `docs/smoke-checklist.md`：自选行情节补「Ops 同步后行业列可见」

## 验收

1. 表有映射且 Redis 行业空 → 自选列表显示行业名  
2. Redis 已有 → 不覆盖  
3. `enrich=false` → `industry` 为空  
4. 相关 pytest + `npm run build` 绿  

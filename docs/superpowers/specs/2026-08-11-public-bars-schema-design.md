# 绿场建表：public 日 K（dbbardata / dbbaroverview）设计

日期：2026-08-11  
状态：已批准（方案 A：Alembic `009` 建表 + 性能索引；**不**自动拉数）  
范围：仅 zak2；不改 zak / vnpy-*；不改 `bar_download` / Ops job 业务逻辑

## 背景

独立演进后 zak2 自有 PG 仅有 `public.alembic_version`，**无** VeighNa 日 K 表。  
既有迁移 `005`/`006` 仅在 `to_regclass('public.dbbardata') IS NOT NULL` 时建索引，绿场不会建表。  
Ops 已有 `fill_watchlist_bars` / `batch_fill_stale` / `batch_download_universe`（Tushare → `dbbardata`），但表缺失时无法写入。  
源库 zak 有约 769 万行日 K；产品约定**不**一次性拷大表，靠 Web 重拉。

## 目标

1. Alembic 升级后绿场具备 `public.dbbardata`、`public.dbbaroverview`（列、PK、唯一约束对齐 VeighNa / 现网 zak）。  
2. 挂上既有日 K 性能索引（与 `alembic/ddl/public_bars.py` 一致）。  
3. 文档说明：upgrade 后于 Ops **手动**跑「补全自选日 K」（需 `TUSHARE_TOKEN`）。

## 非目标

- 本刀**不**自动执行任何 bars fill / universe 下载  
- 不从 zak 导入 `dbbardata` 行数据  
- 不改 `ops_bars_fill` / `bar_download` 语义与 API  
- 不实现分钟 K / tick 表  

## 决策摘要

| 项 | 选择 |
|----|------|
| 建表方式 | Alembic `009_create_public_bars` |
| 拉数 | 运维手动（本刀仅建表） |
| 幂等 | `CREATE TABLE IF NOT EXISTS` + 索引 `IF NOT EXISTS` |

---

## 1. 表结构

对齐现网 zak / `app.models.bars.DbBarData`（写入路径用 real/float）：

### `public.dbbardata`

| 列 | 类型 | 约束 |
|----|------|------|
| id | serial / integer | PK |
| symbol, exchange, interval | varchar | NOT NULL |
| datetime | timestamp | NOT NULL |
| volume, turnover, open_interest | real | NOT NULL |
| open_price, high_price, low_price, close_price | real | NOT NULL |

唯一索引：`(symbol, exchange, interval, datetime)`（名：`dbbardata_symbol_exchange_interval_datetime`）

### `public.dbbaroverview`

| 列 | 类型 | 约束 |
|----|------|------|
| id | serial / integer | PK |
| symbol, exchange, interval | varchar | NOT NULL |
| count | integer | NOT NULL |
| start, end | timestamp | NOT NULL（列名 `end` 需引号） |

唯一索引：`(symbol, exchange, interval)`（名：`dbbaroverview_symbol_exchange_interval`）

### 性能索引

升级末尾执行 `PUBLIC_BAR_INDEX_UP`（及可选 `ANALYZE`），与 `005`/`006` 目标一致；`IF NOT EXISTS` 避免与旧环境冲突。

---

## 2. 迁移与模块

| 路径 | 职责 |
|------|------|
| `backend/alembic/versions/009_create_public_bars.py` | upgrade/downgrade |
| 可选：`backend/alembic/ddl/public_bars.py` | 可增 `CREATE TABLE` SQL 常量，供 009 引用（保持单一真相） |
| `backend/tests/test_alembic_public_bars.py` 或扩现有 migration 测 | 断言 upgrade 后 `to_regclass` 非空 + 唯一索引存在（可用 sqlite/跳过或对测试 PG；若仓库无测 PG，至少纯 SQL 字符串测 / 文档 smoke） |
| `docs/smoke-checklist.md` | upgrade + Ops 补全自选日 K |
| `docs/product-roadmap.md` | 记日 K 绿场建表已补（或近期待办勾掉相关缺口） |

Downgrade：`DROP TABLE IF EXISTS public.dbbardata, public.dbbaroverview CASCADE`（或先 drop indexes 再表；注意仅绿场安全，有数据环境慎用——downgrade 注明）。

---

## 3. 验收

1. 空库或当前 zak2：`alembic upgrade head` → 两表存在，唯一索引与性能索引在。  
2. Ops 手动 `fill_watchlist_bars`（有 token + 自选）可写入行；自选页/市场详情能读日 K（人工可选）。  
3. `./scripts/check.sh` 通过。

## 明确不做（复述）

自动拉数、从 zak 拷日 K、双写桌面、下单。

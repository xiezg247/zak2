# 封板时间深度（limit_list 管线 + 消费）设计

日期：2026-08-06  
状态：已批准（方案 1 + 消费 B）  
范围：仅 zak2；不改 zak / vnpy-*

## 目标

用 Tushare `limit_list_d` 稳定提供 `first_time`，落 PG，并接入龙头评分与雷达/Hub/共振展示。

## 非目标

- TickFlow 分 K 补缺
- 权重 UI / 情绪阶段自适应权重乘子
- 用 `fd_amount` 等重写 `seal_quality`（字段可入库，本刀不改质量公式）
- 改共振权重公式

## 数据源

仅 Tushare `limit_list_d`，`limit_type=U`。  
无 token / 拉取失败：读路径静默降级（无 `first_time`，`seal_time_score=0`）。

## 表：`app.limit_list_daily`

主键：`(trade_date, vt_symbol)`

| 列 | 类型语义 |
|----|----------|
| `trade_date` | `YYYYMMDD` |
| `vt_symbol` | TickFlow 风格，如 `SHSE.600519` |
| `ts_code` | 原始 `600519.SH` |
| `name` | 名称 |
| `limit_times` | 连板 |
| `first_time` / `last_time` | 时钟字符串（如 `0935`） |
| `fd_amount` / `open_times` / `strth` | 封单相关（先存） |
| `updated_at` | ISO 文本 |

建表：与现有日表一致（ORM model + 启动/同步时 `CREATE TABLE IF NOT EXISTS` 若项目已有该模式；否则纯 SQL 迁移脚本跟随现有 ops sync 惯例）。

## 同步 Job

- `job_id`: `sync_limit_list`（Ops 可跑）
- 默认同步最近 1 个交易日（可用 env 扩到少量历史日）
- upsert 当日涨停全量行；写 job meta（条数、交易日）
- 未配置 `TUSHARE_TOKEN` → 明确失败

## 读路径

- `load_first_time_map(db, trade_date?)` → `{vt_symbol: first_time}`
- 当日表空且有 token：懒拉一次 `limit_list_d` 再 upsert 后读
- 纯函数（zak2 自实现，不 import vnpy）：
  - `parse_clock_minutes`
  - `seal_time_score`（与桌面时段一致：09:25–10:30→1.0，至 13:30→0.7，至 15:00→0.5，否则 0）
  - `format_seal_time_label` → `HH:MM 封板`

## 龙头评分

现有 5 维改为 6 维（合计 1.0）：

| 维度 | 权重 |
|------|------|
| `limit_times` | 0.28 |
| `seal_quality` | 0.16 |
| `amount_rank` | 0.16 |
| `seal_time` | 0.12 |
| `net_mf` | 0.15 |
| `sector_strength` | 0.13 |

无 `first_time` → `seal_time` 分项为 0。  
`compute_leader_score` / `rank_leader_pool` 需可注入或查询 map。

结果行字段：`first_time`、`seal_time_score`、`seal_time_label`（可选）。

## 消费挂载

1. `run_leader_screen` / `synth_leader_pick_rows`：attach + 参与打分  
2. `discovery_limit_ladder` 雷达行：有则带 `first_time` / label（不重算龙头分）  
3. 共振侧栏：有则展示 label；不改共振权重  
4. Hub 龙头 Tab：连板旁或 hint 显示封板时刻  

## API（联调）

`GET /api/v1/market/limit-list?trade_date=`  
返回当日涨停摘要；主路径仍为内部 attach，前端可不依赖。

## 错误处理

| 情况 | 行为 |
|------|------|
| 无 token | sync 失败提示；读路径当无时间 |
| Tushare 网络/积分 | sync 记失败；懒拉失败静默 |
| 表空 / 未建 | 懒拉或展示「—」 |

## 测试

- `seal_time_score` 时段边界  
- `compute_leader_score` 有/无 `first_time` 分差  
- sync：mock Tushare upsert（不打真网）  
- API：fixture 下 limit-list / leader 含字段  

## 文档

更新 `docs/gap-vs-desktop.md`、`docs/smoke-checklist.md`。

## 验收

1. Ops 可跑 `sync_limit_list`（有 token 时写入行）  
2. 龙头结果带封板时刻且评分含 `seal_time`  
3. 雷达连板梯队 / 共振侧栏有则显示  
4. pytest + 前端 build 通过  

# zak2 产品路线

## 定位

独立 Web 量化终端：自有 PostgreSQL / Redis / Alembic；不依赖 zak 桌面运行时与 CLI。

## 当前基线

- 登录、自选、选股 Hub、市场/板块/雷达、笔记/Feed、回测薄、AI、Ops
- 进程：`api` + `quote-collector` + `web`
- 数据：Compose 默认自带 PG/Redis；可选 `scripts/import_from_zak.py` 一次性导入

## 近期待办

1. 完成本独立演进落地（Compose / Alembic / `zak2:` 前缀 / 去 CLI 文案 / 导入脚本）
2. ~~Ops planned job 透明化与健康面板打磨~~（已完成 → [spec](./superpowers/specs/2026-08-11-ops-planned-health-polish-design.md)）
3. ~~日 K 绿场建表~~（已完成 → [spec](./superpowers/specs/2026-08-11-public-bars-schema-design.md)）；拉数仍靠 Ops 手动
4. ~~行情 enrich 因子~~（已完成 → [spec](./superpowers/specs/2026-08-11-quote-enrich-design.md)）；~~AI 只读持仓/信号工具~~（已完成 → [spec](./superpowers/specs/2026-08-11-ai-read-positions-signals-design.md)）；候选：其它 Web 体验
5. ~~Ops planned 首批四 job~~（已完成 → [spec](./superpowers/specs/2026-08-11-ops-planned-batch1-design.md)）：`sync_suspend_daily` / `sync_disclosure_calendar` / `prefetch_tushare` / `warm_radar_card_snapshots` 已注册为可跑（默认定时关）
6. ~~Ops planned 第二批~~（已完成 → [spec](./superpowers/specs/2026-08-12-ops-planned-batch2-design.md)）：`prefetch_moneyflow` / `sync_watchlist_financials` 已注册为可跑（默认定时关）
7. ~~Ops planned 第三批~~（已完成 → [spec](./superpowers/specs/2026-08-12-ops-planned-batch3-design.md)）：`warm_watchlist_strategy_cache` / `scan_horizon_outlook` 为可跑占位（恒 skipped）
8. ~~Ops planned 第四批~~（已完成 → [spec](./superpowers/specs/2026-08-12-ops-planned-batch4-design.md)）：`prefetch_concept_board` / `fill_focus_pool_minute` 可跑占位（恒 skipped）；catalog 已无 planned
9. ~~自选列表扩列排序过滤~~（已完成 → [spec](./superpowers/specs/2026-08-12-watchlist-list-sort-filter-design.md)）

## 明确不做（直到本文件改口）

- 与桌面双写同步
- 依赖 zak CLI 完成运维
- 交易下单链路

设计总纲：[docs/superpowers/specs/2026-08-11-zak2-independent-evolution-design.md](./superpowers/specs/2026-08-11-zak2-independent-evolution-design.md)

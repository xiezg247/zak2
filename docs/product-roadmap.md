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
3. ~~行情 enrich 因子~~（已完成 → [spec](./superpowers/specs/2026-08-11-quote-enrich-design.md)）；~~AI 只读持仓/信号工具~~（已完成 → [spec](./superpowers/specs/2026-08-11-ai-read-positions-signals-design.md)）；候选：其它 Web 体验

## 明确不做（直到本文件改口）

- 与桌面双写同步
- 依赖 zak CLI 完成运维
- 交易下单链路

设计总纲：[docs/superpowers/specs/2026-08-11-zak2-independent-evolution-design.md](./superpowers/specs/2026-08-11-zak2-independent-evolution-design.md)

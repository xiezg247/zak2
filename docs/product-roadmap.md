# zak2 产品路线

## 定位

独立 Web 量化终端：自有 PostgreSQL / Redis / Alembic；不依赖 zak 桌面运行时与 CLI。

## 当前基线

- 登录、自选、选股 Hub、市场/板块/雷达、笔记/Feed、回测薄、AI、Ops
- 进程：`api` + `quote-collector` + `web`
- 数据：Compose 默认自带 PG/Redis；可选 `scripts/import_from_zak.py` 一次性导入

## 近期待办

1. ~~完成本独立演进落地~~（已完成 → [总纲](./superpowers/specs/2026-08-11-zak2-independent-evolution-design.md)；收口 → [spec](./superpowers/specs/2026-08-13-independent-evolution-closeout-design.md)）
2. ~~Ops planned job 透明化与健康面板打磨~~（已完成 → [spec](./superpowers/specs/2026-08-11-ops-planned-health-polish-design.md)）
3. ~~日 K 绿场建表~~（已完成 → [spec](./superpowers/specs/2026-08-11-public-bars-schema-design.md)）；拉数仍靠 Ops 手动
4. ~~行情 enrich 因子~~（已完成 → [spec](./superpowers/specs/2026-08-11-quote-enrich-design.md)）；~~AI 只读持仓/信号工具~~（已完成 → [spec](./superpowers/specs/2026-08-11-ai-read-positions-signals-design.md)）；候选：其它 Web 体验
5. ~~Ops planned 首批四 job~~（已完成 → [spec](./superpowers/specs/2026-08-11-ops-planned-batch1-design.md)）：`sync_suspend_daily` / `sync_disclosure_calendar` / `prefetch_tushare` / `warm_radar_card_snapshots` 已注册为可跑（默认定时关）
6. ~~Ops planned 第二批~~（已完成 → [spec](./superpowers/specs/2026-08-12-ops-planned-batch2-design.md)）：`prefetch_moneyflow` / `sync_watchlist_financials` 已注册为可跑（默认定时关）
7. ~~Ops planned 第三批~~（已完成 → [spec](./superpowers/specs/2026-08-12-ops-planned-batch3-design.md)）：`warm_watchlist_strategy_cache` / `scan_horizon_outlook` 当时注册为可跑占位；现状见 #26 / #29（展望/策略启发式）
8. ~~Ops planned 第四批~~（已完成 → [spec](./superpowers/specs/2026-08-12-ops-planned-batch4-design.md)）：`prefetch_concept_board` / `fill_focus_pool_minute` 当时注册为可跑占位（catalog 已无 planned）；现状见 #27 / #30
9. ~~自选列表扩列排序过滤~~（已完成 → [spec](./superpowers/specs/2026-08-12-watchlist-list-sort-filter-design.md)）
10. ~~自选分组管理闭环~~（已完成 → [spec](./superpowers/specs/2026-08-12-watchlist-groups-manage-design.md)）
11. ~~策略看盘 UX 闭环~~（已完成 → [spec](./superpowers/specs/2026-08-12-watchlist-strategy-board-ux-design.md)）
12. ~~持仓与风控 UX 打磨~~（已完成 → [spec](./superpowers/specs/2026-08-12-watchlist-positions-risk-ux-design.md)）
13. ~~选股 Hub 结果表排序过滤~~（已完成 → [spec](./superpowers/specs/2026-08-12-screener-hub-result-sort-filter-design.md)）
14. ~~选股 Hub 运行历史打磨~~（已完成 → [spec](./superpowers/specs/2026-08-12-screener-hub-history-ux-design.md)）
15. ~~选股 Hub 批量入自选~~（已完成 → [spec](./superpowers/specs/2026-08-12-screener-hub-batch-watchlist-design.md)）
16. ~~雷达首屏空态 UX~~（已完成 → [spec](./superpowers/specs/2026-08-12-radar-empty-loading-ux-design.md)）
17. ~~雷达展望读路径薄壳~~（已完成 → [spec](./superpowers/specs/2026-08-12-radar-horizon-shell-ux-design.md)）
18. ~~雷达卡片筛选排序~~（已完成 → [spec](./superpowers/specs/2026-08-12-radar-card-filter-sort-design.md)）
19. ~~板块资金表过滤排序~~（已完成 → [spec](./superpowers/specs/2026-08-12-sector-flow-sort-filter-design.md)）
20. ~~市场排行过滤排序~~（已完成 → [spec](./superpowers/specs/2026-08-12-market-rank-sort-filter-design.md)）
21. ~~市场情绪周期展示 UX~~（已完成 → [spec](./superpowers/specs/2026-08-12-market-emotion-cycle-ux-design.md)）
22. ~~市场与板块页眉互链~~（已完成 → [spec](./superpowers/specs/2026-08-12-market-sector-crosslink-design.md)）
23. ~~Feed 时间线过滤空态~~（已完成 → [spec](./superpowers/specs/2026-08-12-feed-timeline-filter-ux-design.md)）
24. ~~AI 会话过滤与确认卡 UX~~（已完成 → [spec](./superpowers/specs/2026-08-12-ai-session-confirm-ux-design.md)）
25. ~~自选列表列偏好~~（已完成 → [spec](./superpowers/specs/2026-08-12-watchlist-column-prefs-design.md)）
26. ~~雷达展望启发式写读闭环~~（已完成 → [spec](./superpowers/specs/2026-08-12-radar-horizon-heuristic-design.md)）
27. ~~Ops 三 skipped job 薄做实~~（已完成 → [spec](./superpowers/specs/2026-08-12-ops-skipped-jobs-thin-design.md)）
28. ~~自选分组排序与批量移组~~（已完成 → [spec](./superpowers/specs/2026-08-12-watchlist-groups-sort-batch-design.md)）
29. ~~策略信号日 K 双均线启发式~~（已完成 → [spec](./superpowers/specs/2026-08-13-strategy-ma-signal-heuristic-design.md)）
30. ~~关注池 1m K 真下载~~（已完成 → [spec](./superpowers/specs/2026-08-13-focus-pool-1m-download-design.md)）
31. ~~笔记侧栏过滤与空态~~（已完成 → [spec](./superpowers/specs/2026-08-13-notes-sidebar-filter-ux-design.md)）
32. ~~笔记安全操作与研报 Tab 薄打磨~~（已完成 → [spec](./superpowers/specs/2026-08-13-notes-safety-reports-ux-design.md)）
33. ~~回测历史过滤与空态~~（已完成 → [spec](./superpowers/specs/2026-08-13-backtest-history-filter-ux-design.md)）
34. ~~回测画像填参与失败 Ops 引导~~（已完成 → [spec](./superpowers/specs/2026-08-13-backtest-profile-ops-ux-design.md)）
35. ~~Feed 左侧订阅过滤~~（已完成 → [spec](./superpowers/specs/2026-08-13-feed-subscription-filter-ux-design.md)）
36. ~~市场排行空态与日 K Ops 引导~~（已完成 → [spec](./superpowers/specs/2026-08-13-market-rank-bars-ops-ux-design.md)）
37. ~~Feed「仅启用」订阅过滤~~（已完成 → [spec](./superpowers/specs/2026-08-13-feed-enabled-only-filter-ux-design.md)）
38. ~~板块空态 Ops 与雷达共振过滤~~（已完成 → [spec](./superpowers/specs/2026-08-13-sector-ops-radar-resonance-filter-ux-design.md)）
39. ~~雷达卡片详情行操作~~（已完成 → [spec](./superpowers/specs/2026-08-13-radar-card-detail-actions-ux-design.md)）
40. ~~雷达详情反馈清空与操作钮样式~~（已完成 → [spec](./superpowers/specs/2026-08-13-radar-detail-msg-btn-polish-ux-design.md)）

## 明确不做（直到本文件改口）

- 与桌面双写同步
- 依赖 zak CLI 完成运维
- 交易下单链路

设计总纲：[docs/superpowers/specs/2026-08-11-zak2-independent-evolution-design.md](./superpowers/specs/2026-08-11-zak2-independent-evolution-design.md)

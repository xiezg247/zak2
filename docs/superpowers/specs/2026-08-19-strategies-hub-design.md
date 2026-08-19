# 策略总览页 + 全局「策略」入口 设计

日期：2026-08-19

## 背景与目标

当前策略能力分散：看板页 `/board` 提供三种信号模式（启发式确认 / 回测双均线 / 趋势均线）的策略看盘，回测页 `/backtest` 提供 vnpy CTA 双均线与趋势均线的回测。全局侧边栏（`AppShell.vue`）的「交易」组中「看板」「回测」平铺，缺少一个集中查看策略状态与信号的入口。

本需求在全局侧边栏新增「策略」入口，落地一个**纯前端**的策略总览页 `/strategies`：

- 集中展示三种信号模式的实时状态与信号明细
- 展示回测策略清单（双均线 / 趋势双均线 ADX）
- 一键跳转看板（带模式）与回测

## 范围

只改前端，不做后端改动：

- `frontend/src/views/StrategyView.vue`（新增）
- `frontend/src/components/AppShell.vue`（导航项 + active 类型）
- `frontend/src/components/NavIcon.vue`（新图标）
- `frontend/src/router/index.ts`（路由）
- `frontend/src/views/BoardView.vue`（读取 `signal_mode` query 并高亮对应模式）

复用现有 API：`watchlistApi.strategyBoard({ signalMode })` 与 `backtestApi.strategies()`。

## 导航改动

「交易」组内「看板」之后插入「策略」入口：

- `active` 联合类型新增 `'strategies'`
- `NavKey` 类型新增 `'strategies'`
- `NavIcon.vue` 新增 `strategies` 图标（Heroicons 风格 stroke，与现有图标一致）
- 路由 `/strategies` → `StrategyView.vue`

## 页面结构（StrategyView.vue）

### 顶部：策略信号概览

并行拉取三个 `strategyBoard({ signalMode })`（heuristic_v2 / double_ma / trend_ma），三张卡片，每张展示：

- 模式名（启发式确认 / 回测双均线 / 趋势均线）
- `config_key`
- 信号数 `signals.length`
- 数据来源 `source`（redis / pg / none 等）
- `as_of`
- 仓位建议 `risk_summary.actual_position_pct`

操作：

- 「去看板」：跳转 `/board?signal_mode=<mode>`，BoardView 挂载时读取该 query 覆盖 localStorage 中的模式并高亮
- 「同参回测」：复用 `frontend/src/lib/boardBacktestParams.ts` 的 `buildAlignedBacktestQuery` 生成 query，跳转 `/backtest`

空数据提示：可去 Ops 跑 `warm_watchlist_strategy_cache` 预热（链接到 `/ops`）。

### 中部：回测策略清单

`backtestApi.strategies()` 返回的双均线 / 趋势双均线（ADX），两卡展示描述、interval、engine，带「去回测」按钮。

### 底部：信号明细

默认选中启发式模式，可切换三种模式，表格列与看板信号区一致（代码 / 名称 / 现价 / 信号 / 强度 / 摘要），选中行跳转 `/watchlist?symbol=<vt>`。

## 数据流与交互

- 挂载时并行加载：3 个 strategyBoard + strategies
- 「刷新」按钮手动刷新全部
- 开市时轻量轮询：沿用 `useQuoteNotify` 模式（WS + 慢轮询），休市不轮询
- 页面 `document.hidden` 时暂停刷新
- 错误汇总展示，不阻塞其他卡片

## 错误处理

- 单个 strategyBoard 失败：该卡片显示错误，其余卡片正常
- 三个全失败：展示汇总错误与重试
- strategies 失败：回测策略区显示错误，不影响信号区

## 验收标准

1. 侧边栏「交易」组出现「策略」入口，位于「看板」之后，图标与现有导航风格一致
2. `/strategies` 加载显示三种信号模式卡片 + 回测策略清单 + 信号明细
3. 「去看板」携带正确 `signal_mode`；看板页能读取该参数并高亮对应模式
4. 空缓存时给出可操作的提示链接
5. `npm run build`（vue-tsc + vite）通过

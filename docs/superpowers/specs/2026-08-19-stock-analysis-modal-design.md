# 个股分析全局弹窗 设计

日期：2026-08-19

## 背景与目标

市场/自选/看板/策略总览等列表页都能看到个股，但查看个股信息需要分散在各页面点开不同弹窗（市场页有 K 线/基本面 modal，看板页有信号区）。缺少一个统一的个股分析入口。

本需求落地一个**全局个股分析弹窗**：从任意列表点代码统一打开，Tab 分页聚合 行情/K线、基本面、策略信号、雷达共振、AI 研报、笔记 六个模块。

## 范围

纯前端改动，零后端改动。复用现有 API：

| 模块 | API |
|---|---|
| 行情/K线 | `watchlistApi.quotes`、`watchlistApi.bars` |
| 基本面 | `watchlistApi.fundamentals` |
| 策略信号 | `watchlistApi.strategyBoard({ signalMode })` × 3 |
| 雷达共振 | `marketApi.radarResonance` |
| AI 研报 | `aiApi.streamTeam`、`contentApi.teamReportsPage`、`contentApi.teamReport` |
| 笔记 | `contentApi.memo`、`saveMemo`、`entriesPage`、`addEntry`、`deleteEntry` |

## 组件与状态

### 新增 `frontend/src/composables/useStockAnalysis.ts`

全局单例分析弹窗状态（模块级 `let` + `ref`，不依赖 Pinia）：

- `open(vt_symbol, name?)`：打开弹窗，重置 tab 为 `quote`，清空已加载数据
- `close()`：关闭
- 状态暴露：`vtSymbol`、`name`、`isOpen`、`activeTab`
- `loadedTabs: Set<TabKey>`：已加载过的 tab，切回不再重新请求

### 新增 `frontend/src/components/StockAnalysisModal.vue`

- `<Teleport to="body">` 弹窗，复用 `chart-overlay`/`chart-modal` 样式风格
- 顶部：标的名称 + vt_symbol + 关闭按钮
- Tab 栏：行情 / 基本面 / 策略信号 / 雷达 / AI研报 / 笔记
- Esc 关闭、点击遮罩关闭（复用市场页 modal 模式）
- 每个 tab 首切才请求数据，期间显示「加载中…」，失败显示错误 + 重试按钮

### 挂载方式

在各接入页面视图内挂 `<StockAnalysisModal />`（保持各页面自包含，不侵入 `App.vue`）。

## Tab 详情

### 行情/K线（默认 tab）
- 打开弹窗即加载（不等待切 tab）
- 行情摘要 grid：现价/涨跌额/涨跌幅/换手/量比/振幅/成交额/总市值/行业
- K 线：日K/1分K 切换 + 根数 chips（复用市场页交互），CandleChart 渲染
- 数据源：`watchlistApi.quotes`（单标的）、`watchlistApi.bars(vt, interval, limit)`

### 基本面
- `watchlistApi.fundamentals(vt)`：财报快照（营收/净利/同比/ROE/负债率）+ 披露日历表
- 无财报/无披露时提示「去 Ops 同步」链接（复用市场页文案）

### 策略信号
- 并行 `strategyBoard` 三轨（heuristic_v2/double_ma/trend_ma）
- 过滤出 `vt_symbol === 当前标的` 的信号，表格展示：模式/信号/强度/摘要/参考买入/参考卖出
- 全部无信号时显示「无信号，可去 Ops 跑 warm_watchlist_strategy_cache」

### 雷达共振
- `marketApi.radarResonance({ top_n: 100, min_cards: 1 })`
- 过滤出该 vt 的条目：共振分 / 卡片数 / 卡片标题 / 封板时间
- 无条目显示「暂无共振」

### AI 研报
- 快速/深度模式 radio（复用 AiView 交互）
- 「生成研报」按钮 → `aiApi.streamTeam(vt, handlers, undefined, mode)` 流式展示
- 生成中显示 agent 状态（`onEvent` 的 kind=started/score/delta），支持生成完成提示
- 下方历史报告列表：`contentApi.teamReportsPage(vt, 1, 20)`，点击加载 `contentApi.teamReport(id)` 详情（MarkdownView 渲染 body）
- 首次打开该 tab 时同时拉取历史列表

### 笔记
- 速记：`contentApi.memo` 加载，textarea 编辑 + 保存 `contentApi.saveMemo`
- 条目：`contentApi.entriesPage(vt)` 列表，新增 `addEntry`、删除 `deleteEntry`
- 布局参考 NotesView 的 memo/entries 交互

## 接入点（代码处加「分析」按钮）

| 页面 | 位置 |
|---|---|
| `MarketView` | 表格操作区 `row-ops` 内加「分析」icon 按钮 |
| `WatchlistView` | 列表行内加「分析」icon 按钮 |
| `BoardView` | 信号区每行「入名单/移出」旁加「分析」；持仓区行内加 |
| `StrategyView` | 信号明细每行代码旁加「分析」按钮 |
| `RadarView` | 共振/卡片行内若含 `vt_symbol` 加「分析」按钮 |

统一调用 `useStockAnalysis().open(vt, name)`，并挂 `<StockAnalysisModal />`。

## 交互与错误处理

- 打开弹窗即加载行情 tab；其余 tab 首次切换才请求（懒加载）
- 已加载 tab 切回不重新请求；AI 研报重新生成属手动操作
- 每个 tab 独立 loading/error 状态，互不阻塞
- AI 研报生成中禁止重复触发；可手动刷新历史报告列表
- 无 LLM 配置时研报 tab 提示「未配置 LLM_API_KEY」（复用 AiView 逻辑：`aiApi.status`）

## 验收标准

1. 市场/自选/看板/策略总览/雷达页均可点代码打开分析弹窗
2. 默认行情 tab 展示摘要 + K 线，日K/1分K 可切换
3. 六个 tab 切换正常，懒加载有效，错误独立展示可重试
4. AI 研报快速/深度可生成、流式展示，历史报告可查看详情
5. 笔记速记保存、条目增删可用
6. `npm run build`（vue-tsc + vite）与 `npm run lint:check` 通过

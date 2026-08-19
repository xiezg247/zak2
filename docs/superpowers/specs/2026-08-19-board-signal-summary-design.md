# 看板信号统计卡设计

> 日期：2026-08-19

## 背景

看板页（`frontend/src/views/BoardView.vue`）当前顶部只有「仓位与风控」一张卡，下方信号表直接平铺所有信号，缺少对「买入 / 卖出 / 中性」的概览与快速聚焦能力。用户希望优化顶部概览布局。

## 目标

在不改动后端的前提下，新增一张**信号统计卡**，提供：

1. 三块计数概览（买入 / 卖出 / 中性）
2. 点击统计块可过滤下方信号表，再次点击取消过滤

## 设计

### 布局

`summary-grid` 目前为单列，容纳风控卡。改为双列：左侧「仓位与风控」，右侧「信号统计」。窄屏（≤900px）回退单列（沿用现有媒体查询）。

### 数据来源

信号来自 `board.signals`（`StrategySignalRow[]`），其中：

- `signal === 'buy'` → 买入
- `signal === 'sell'` → 卖出
- 其余（空字符串等）→ 中性

无需后端改动。

### 组件行为

- `signalFilter = ref<'' | 'buy' | 'sell'>('')`，空表示不过滤
- `signalCounts` computed：统计三类数量
- `filteredSignals` computed：按 `signalFilter` 过滤 `board.signals`
- 点击统计块：`signalFilter.value = signalFilter.value === key ? '' : key`
- 表格渲染改用 `filteredSignals`；空态文案随过滤状态提示「该分类暂无信号」
- 过滤只影响展示，不影响现有「行点击选中 + 用选中」逻辑（选中仍针对全量信号）

### 视觉

- 三块统计样式沿用涨跌配色：买入 `.up`（红）、卖出 `.down`（绿）、中性 `.muted`
- 选中态使用 `--brand-light` 背景 + `--brand` 边框（与现有 `.ghost.on`、`.tabs button.on` 一致）
- 统计数字大号展示（约 1.5rem），标签小号

## 不改动

- 后端 API、风控卡逻辑、信号表列结构均保持现状
- 不做仓位/市值/浮盈等其它统计块（用户明确仅选信号统计）

## 验证

- `cd frontend && npm run build` 通过（vue-tsc + vite）
- `npm run lint:check`、`npm run format:check` 通过

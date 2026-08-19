# 看板信号统计卡实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 看板顶部新增「信号统计」卡，展示买入/卖出/中性计数，点击可过滤下方信号表。

**Architecture:** 纯前端改动。`summary-grid` 改双列，右侧新增信号统计卡；`signalFilter` ref + computed 派生 `signalCounts` 与 `filteredSignals`，表格改用过滤后数据，空态文案随过滤状态变化。

**Tech Stack:** Vue 3 + TypeScript + Vite（`frontend/src/views/BoardView.vue`）

## Global Constraints

- 前端 TypeScript 必须通过 `vue-tsc` 与 `eslint`（`npm run build` 通过）
- prettier 格式通过（`npm run format:check`）
- 不加后端改动；不新增其它统计块（仅信号统计）
- 沿用现有配色变量：买入 `.up`、卖出 `.down`、中性 `.muted`；选中态 `--brand-light` + `--brand`
- 过滤只影响展示，不影响现有「行点击选中 + 用选中」逻辑
- commit message 用简体中文，格式 `<type>(<scope>): <简述>`

---

### Task 1: 信号统计卡

**Files:**
- Modify: `frontend/src/views/BoardView.vue`

**Interfaces:**
- Consumes: `board.signals: StrategySignalRow[]`（字段 `signal: 'buy' | 'sell' | ''`）
- Produces:
  - `signalFilter: Ref<'all' | 'buy' | 'sell' | 'neutral'>`（`all`=不过滤）
  - `signalCounts: ComputedRef<{ buy: number; sell: number; neutral: number }>`
  - `filteredSignals: ComputedRef<StrategySignalRow[]>`

- [ ] **Step 1: script 区新增过滤状态与派生数据**

在 `frontend/src/views/BoardView.vue` 的 `<script setup>` 中，`const panelMax = 10` 之后追加：

```typescript
const signalFilter = ref<'all' | 'buy' | 'sell' | 'neutral'>('all')

const signalCounts = computed(() => {
  let buy = 0
  let sell = 0
  let neutral = 0
  for (const s of board.value?.signals || []) {
    if (s.signal === 'buy') buy += 1
    else if (s.signal === 'sell') sell += 1
    else neutral += 1
  }
  return { buy, sell, neutral }
})

const filteredSignals = computed(() => {
  const all = board.value?.signals || []
  if (signalFilter.value === 'all') return all
  if (signalFilter.value === 'neutral') {
    return all.filter((s) => s.signal !== 'buy' && s.signal !== 'sell')
  }
  return all.filter((s) => s.signal === signalFilter.value)
})
```

- [ ] **Step 2: 模板区新增统计卡**

在 `summary-grid` 中「仓位与风控」`section` 之后、`</div>` 之前追加：

```html
<section class="card signal-summary">
  <h3>
    信号统计
    <span class="muted">{{ board?.signals.length || 0 }}</span>
  </h3>
  <div class="signal-blocks">
    <button
      type="button"
      class="signal-block up"
      :class="{ on: signalFilter === 'buy' }"
      @click="signalFilter = signalFilter === 'buy' ? 'all' : 'buy'"
    >
      <span class="signal-count">{{ signalCounts.buy }}</span>
      <span class="signal-label">买入</span>
    </button>
    <button
      type="button"
      class="signal-block down"
      :class="{ on: signalFilter === 'sell' }"
      @click="signalFilter = signalFilter === 'sell' ? 'all' : 'sell'"
    >
      <span class="signal-count">{{ signalCounts.sell }}</span>
      <span class="signal-label">卖出</span>
    </button>
    <button
      type="button"
      class="signal-block"
      :class="{ on: signalFilter === 'neutral' }"
      @click="signalFilter = signalFilter === 'neutral' ? 'all' : 'neutral'"
    >
      <span class="signal-count">{{ signalCounts.neutral }}</span>
      <span class="signal-label">中性</span>
    </button>
  </div>
  <p v-if="signalFilter !== 'all'" class="muted tip">
    正在筛选「{{ signalFilter === 'buy' ? '买入' : signalFilter === 'sell' ? '卖出' : '中性' }}」信号，再次点击取消
  </p>
</section>
```

- [ ] **Step 3: 信号表改为使用过滤后数据**

信号表 `v-for="row in board.signals"` 改为 `v-for="row in filteredSignals"`；空态行 `colspan="7"` 文案随过滤状态变化：

```html
<tr v-for="row in filteredSignals" :key="row.vt_symbol" ...>

<tr v-if="!filteredSignals.length">
  <td colspan="7" class="empty">
    {{
      signalFilter !== 'all'
        ? '该分类暂无信号'
        : '无信号（可先编辑名单，或确认策略 cache 已写入）'
    }}
  </td>
</tr>
```

- [ ] **Step 4: 样式区新增统计卡样式**

在 `<style scoped>` 中，`.risk-grid` 规则之后追加：

```css
.signal-summary {
  display: grid;
  gap: 10px;
  align-content: start;
}
.signal-blocks {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}
.signal-block {
  display: grid;
  gap: 4px;
  place-items: center;
  padding: 12px 8px;
  border: 1px solid var(--border);
  border-radius: 0.75rem;
  background: var(--surface);
  cursor: pointer;
  transition:
    background 0.15s ease,
    border-color 0.15s ease,
    box-shadow 0.15s ease;
}
.signal-block:hover {
  border-color: var(--brand-soft);
}
.signal-block.on {
  background: var(--brand-light);
  border-color: var(--brand);
  box-shadow: 0 0 0 3px rgba(230, 100, 50, 0.15);
}
.signal-count {
  font-size: 1.5rem;
  font-weight: 600;
  line-height: 1.1;
}
.signal-label {
  font-size: 0.78rem;
  color: var(--muted);
}
.signal-block.up .signal-count {
  color: var(--danger);
}
.signal-block.down .signal-count {
  color: var(--ok);
}
```

- [ ] **Step 5: summary-grid 改双列**

`.summary-grid` 规则改为双列，并更新媒体查询：

```css
.summary-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  align-items: start;
}
```

媒体查询（≤900px）中追加 `.summary-grid` 回退单列：

```css
@media (max-width: 900px) {
  .summary-grid,
  .board-grid,
  .pos-grid,
  .risk-grid {
    grid-template-columns: 1fr;
  }
}
```

- [ ] **Step 6: 构建验证**

Run: `cd frontend && npm run build`
Expected: `vue-tsc` + `vite build` 通过

Run: `cd frontend && npm run lint:check && npm run format:check`
Expected: 通过

- [ ] **Step 7: 提交**

```bash
git add frontend/src/views/BoardView.vue
git commit -m "feat(ui): 看板新增信号统计卡

顶部概览买入/卖出/中性计数，点击可过滤信号表。"
```

# 个股分析全局弹窗 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 落地全局个股分析弹窗：从任意列表点代码打开，Tab 聚合 行情/K线、基本面、策略信号、雷达共振、AI 研报、笔记 六模块。

**Architecture:** 纯前端改动，零后端。新增 `useStockAnalysis` 组合式提供全局单例弹窗状态 + `StockAnalysisModal` 组件（Teleport 弹窗，六 tab 懒加载）；在 Market/Watchlist/Board/Strategy/Radar 五个页面挂载组件并接入「分析」按钮。

**Tech Stack:** Vue 3 `<script setup lang="ts">`、vue-router、Vite、TypeScript。验证用 `npm run build`（vue-tsc + vite）与 `npm run lint:check`。

## Global Constraints

- 前端源码在 `frontend/`，命令均在 `frontend/` 下执行。
- 零后端改动，全部复用现有 API（`watchlistApi`、`marketApi`、`aiApi`、`contentApi`）。
- 弹窗样式沿用 `chart-overlay`/`chart-modal` 风格（市场页已有），新组件自带 scoped 样式，不修改全局 CSS。
- Tab 懒加载：打开弹窗即加载行情 tab，其余 tab 首次切换才请求；`loadedTabs: Set` 记录已加载，切回不重复请求。
- AI 研报 tab 复用 `aiApi.streamTeam` 的流式处理（参考 `AiView.vue` 的 `runTeam` handlers 模式）。
- 提交前需用户确认；commit message 简体中文，格式 `<type>(<scope>): <简述>`。

---

### Task 1: useStockAnalysis 组合式 + StockAnalysisModal 骨架

**Files:**
- Create: `frontend/src/composables/useStockAnalysis.ts`
- Create: `frontend/src/components/StockAnalysisModal.vue`

**Interfaces:**
- Produces:
  - `useStockAnalysis()` → `{ isOpen, vtSymbol, name, activeTab, loadedTabs, open(vt, name?), close() }`
  - `<StockAnalysisModal />`：全局弹窗骨架，含 tab 栏（六个 tab 文案）、关闭按钮、Esc/遮罩关闭；各 tab 内容占位插槽由后续任务填充

- [ ] **Step 1: 创建 useStockAnalysis.ts**

创建 `frontend/src/composables/useStockAnalysis.ts`：

```ts
import { ref } from 'vue'

export type AnalysisTabKey =
  | 'quote'
  | 'fundamental'
  | 'signal'
  | 'radar'
  | 'ai'
  | 'notes'

const isOpen = ref(false)
const vtSymbol = ref('')
const name = ref('')
const activeTab = ref<AnalysisTabKey>('quote')
const loadedTabs = ref<Set<AnalysisTabKey>>(new Set())

export function useStockAnalysis() {
  function open(vt: string, label = '') {
    vtSymbol.value = vt.trim()
    name.value = label
    activeTab.value = 'quote'
    loadedTabs.value = new Set()
    isOpen.value = true
  }
  function close() {
    isOpen.value = false
    vtSymbol.value = ''
    name.value = ''
  }
  function markLoaded(tab: AnalysisTabKey) {
    loadedTabs.value = new Set([...loadedTabs.value, tab])
  }
  function isLoaded(tab: AnalysisTabKey): boolean {
    return loadedTabs.value.has(tab)
  }
  return { isOpen, vtSymbol, name, activeTab, open, close, markLoaded, isLoaded }
}
```

- [ ] **Step 2: 创建 StockAnalysisModal.vue 骨架（script + template 首部）**

创建 `frontend/src/components/StockAnalysisModal.vue`，script 部分：

```vue
<script setup lang="ts">
import { computed, onUnmounted } from 'vue'
import { useStockAnalysis, type AnalysisTabKey } from '../composables/useStockAnalysis'

const analysis = useStockAnalysis()

const TABS: { key: AnalysisTabKey; label: string }[] = [
  { key: 'quote', label: '行情' },
  { key: 'fundamental', label: '基本面' },
  { key: 'signal', label: '策略信号' },
  { key: 'radar', label: '雷达' },
  { key: 'ai', label: 'AI研报' },
  { key: 'notes', label: '笔记' },
]

const displayName = computed(
  () => analysis.name.value || analysis.vtSymbol.value || '—',
)

function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape' && analysis.isOpen.value) analysis.close()
}

function switchTab(tab: AnalysisTabKey) {
  analysis.activeTab.value = tab
}

window.addEventListener('keydown', onKeydown)
onUnmounted(() => window.removeEventListener('keydown', onKeydown))
</script>
```

template 部分（tab 内容区占位，各 tab 由后续任务填充）：

```html
<template>
  <Teleport to="body">
    <div v-if="analysis.isOpen.value" class="stock-overlay" @click.self="analysis.close()">
      <div class="stock-modal" role="dialog" aria-modal="true" aria-label="个股分析">
        <div class="stock-head">
          <strong>{{ displayName }}</strong>
          <span class="mono muted">{{ analysis.vtSymbol.value }}</span>
          <div class="spacer"></div>
          <button type="button" class="icon-btn" title="关闭" @click="analysis.close()">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
              stroke-linecap="round" stroke-linejoin="round">
              <path d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <div class="stock-tabs">
          <button
            v-for="t in TABS"
            :key="t.key"
            type="button"
            :class="{ on: analysis.activeTab.value === t.key }"
            @click="switchTab(t.key)"
          >
            {{ t.label }}
          </button>
        </div>

        <div class="stock-body">
          <!-- 各 tab 内容由后续任务填充 -->
        </div>
      </div>
    </div>
  </Teleport>
</template>
```

样式部分（scoped，沿用 market 弹窗风格）：

```html
<style scoped>
.stock-overlay {
  position: fixed;
  inset: 0;
  z-index: 1000;
  display: grid;
  place-items: center;
  background: rgba(0, 0, 0, 0.45);
  padding: 24px;
}
.stock-modal {
  width: 100%;
  max-width: 900px;
  max-height: 88vh;
  display: grid;
  grid-template-rows: auto auto 1fr;
  gap: 12px;
  padding: 16px 18px;
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: 0.875rem;
  box-shadow: var(--shadow-panel);
}
.stock-head {
  display: flex;
  align-items: baseline;
  gap: 8px;
}
.stock-head strong {
  font-size: 1rem;
}
.stock-head .mono {
  font-size: 0.78rem;
}
.stock-head .spacer {
  flex: 1;
}
.stock-tabs {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  border-bottom: 1px solid var(--line);
  padding-bottom: 10px;
}
.stock-tabs button {
  background: transparent;
  border: 1px solid transparent;
  color: var(--muted);
  border-radius: 0.5rem;
  padding: 6px 12px;
  font-size: 0.8125rem;
  cursor: pointer;
}
.stock-tabs button:hover {
  color: var(--ink);
}
.stock-tabs button.on {
  background: var(--brand-light);
  color: var(--brand);
  border-color: var(--brand-soft);
  font-weight: 500;
}
.stock-body {
  min-height: 0;
  overflow: auto;
  display: grid;
  gap: 12px;
}
.icon-btn {
  display: inline-grid;
  place-items: center;
  width: 26px;
  height: 24px;
  padding: 0;
  border: 1px solid var(--line);
  border-radius: 0.4rem;
  background: transparent;
  color: var(--ink-muted);
  cursor: pointer;
}
.icon-btn:hover {
  background: var(--surface-muted);
  border-color: var(--brand);
  color: var(--brand);
}
.icon-btn svg {
  width: 15px;
  height: 15px;
}
.mono {
  font-family: var(--mono);
}
.muted {
  color: var(--muted);
}
</style>
```

- [ ] **Step 3: 验证构建**

Run: `npm run build`
Expected: PASS（该组件暂未在任何页面挂载，仅作为独立 chunk 编译通过）

---

### Task 2: 行情/K线 tab

**Files:**
- Modify: `frontend/src/components/StockAnalysisModal.vue`
- Modify: `frontend/src/api/watchlist.ts`（新增 `QuoteOut` 类型 + `quotes()` 封装，后端 `/watchlist/quotes` 已存在）

**Interfaces:**
- Consumes: `watchlistApi.quotes(vt)`（本任务 Step 1 新增封装）、`watchlistApi.bars(vt, interval, limit)`、`CandleChart`。
- Produces: `quote` tab 展示行情摘要 grid + K 线（日K/1分K 切换）。

- [ ] **Step 1: watchlist.ts 新增 QuoteOut 类型与 quotes() 封装**

在 `frontend/src/api/watchlist.ts` 中，`Fundamentals` 类型之后追加：

```ts
export type QuoteOut = {
  symbol: string
  exchange: string
  vt_symbol: string
  tf_symbol: string
  name: string
  last_price: number
  change_pct: number
  turnover_rate: number
  volume: number
  amount: number
  amplitude: number
  volume_ratio: number
  industry: string
}
```

在 `watchlistApi` 对象内、`bars` 方法之前追加：

```ts
  quotes: (symbols: string) =>
    api<QuoteOut[]>(`/api/v1/watchlist/quotes?symbols=${encodeURIComponent(symbols)}`),
```

- [ ] **Step 2: script 增加行情状态**

在 `StockAnalysisModal.vue` script 中追加：

```ts
import { ref, watch } from 'vue'
import CandleChart from './CandleChart.vue'
import { watchlistApi, type QuoteOut } from '../api/watchlist'

const quote = ref<QuoteOut | null>(null)
const quoteErr = ref('')
const quoteLoading = ref(false)
const barInterval = ref<'d' | '1m'>('d')
const barLimit = ref(90)
const bars = ref<{ datetime: string; open: number; high: number; low: number; close: number; volume: number }[]>([])
const barsErr = ref('')
const barsLoading = ref(false)

const barLimitChoices = computed(() => (barInterval.value === '1m' ? [240, 480, 1200] : [60, 90, 120]))

async function loadQuote() {
  if (!analysis.vtSymbol.value || analysis.isLoaded('quote')) return
  quoteLoading.value = true
  quoteErr.value = ''
  try {
    const quotes = await watchlistApi.quotes(analysis.vtSymbol.value)
    quote.value = quotes.find((q) => q.vt_symbol === analysis.vtSymbol.value) || null
    analysis.markLoaded('quote')
  } catch (e) {
    quoteErr.value = e instanceof Error ? e.message : '行情加载失败'
  } finally {
    quoteLoading.value = false
  }
}

async function loadBars() {
  if (!analysis.vtSymbol.value) return
  barsLoading.value = true
  barsErr.value = ''
  try {
    const resp = await watchlistApi.bars(analysis.vtSymbol.value, barInterval.value, barLimit.value)
    bars.value = resp.bars
  } catch (e) {
    barsErr.value = e instanceof Error ? e.message : '无 K 线'
  } finally {
    barsLoading.value = false
  }
}

watch(
  () => analysis.activeTab.value,
  (tab) => {
    if (tab === 'quote' && analysis.vtSymbol.value && !analysis.isLoaded('quote')) void loadQuote()
  },
)

watch(
  () => analysis.vtSymbol.value,
  (vt) => {
    if (vt) void loadQuote()
  },
)
```

- [ ] **Step 3: template 的 quote tab 内容**

在 `stock-body` 内追加（`v-if="analysis.activeTab.value === 'quote'"`）：

```html
<div v-if="analysis.activeTab.value === 'quote'" class="quote-tab">
  <p v-if="quoteLoading" class="muted">加载行情…</p>
  <p v-else-if="quoteErr" class="err">{{ quoteErr }}</p>
  <template v-else-if="quote">
    <div class="quote-grid">
      <div class="q-item"><span class="q-label">现价</span><span class="q-value">{{ quote.last_price ? quote.last_price.toFixed(2) : '—' }}</span></div>
      <div class="q-item"><span class="q-label">涨跌幅%</span><span class="q-value" :class="{ up: (quote.change_pct || 0) > 0, down: (quote.change_pct || 0) < 0 }">{{ quote.change_pct ? quote.change_pct.toFixed(2) : '—' }}</span></div>
      <div class="q-item"><span class="q-label">换手%</span><span class="q-value">{{ quote.turnover_rate ? quote.turnover_rate.toFixed(2) : '—' }}</span></div>
      <div class="q-item"><span class="q-label">量比</span><span class="q-value">{{ quote.volume_ratio ? quote.volume_ratio.toFixed(2) : '—' }}</span></div>
      <div class="q-item"><span class="q-label">振幅%</span><span class="q-value">{{ quote.amplitude ? quote.amplitude.toFixed(2) : '—' }}</span></div>
      <div class="q-item"><span class="q-label">成交量</span><span class="q-value">{{ fmtAmount(quote.volume) }}</span></div>
      <div class="q-item"><span class="q-label">成交额</span><span class="q-value">{{ fmtAmount(quote.amount) }}</span></div>
      <div class="q-item"><span class="q-label">行业</span><span class="q-value">{{ quote.industry || '—' }}</span></div>
    </div>
    <div class="bar-controls">
      <div class="limits">
        <button type="button" class="chip" :class="{ on: barInterval === 'd' }" @click="switchInterval('d')">日K</button>
        <button type="button" class="chip" :class="{ on: barInterval === '1m' }" @click="switchInterval('1m')">1分</button>
      </div>
      <div class="limits">
        <button v-for="n in barLimitChoices" :key="n" type="button" class="chip" :class="{ on: barLimit === n }" @click="switchBarLimit(n)">
          {{ barInterval === '1m' ? `${n}根` : `${n}日` }}
        </button>
      </div>
    </div>
    <p v-if="barsLoading" class="muted">加载 K 线…</p>
    <p v-else-if="barsErr" class="err">{{ barsErr }}</p>
    <div v-else-if="bars.length" class="chart">
      <CandleChart :bars="bars" :height="340" :interval="barInterval" />
    </div>
    <p v-else class="muted">暂无 K 线</p>
  </template>
  <p v-else class="muted">无行情数据</p>
</div>
```

- [ ] **Step 4: script 补充辅助函数**

在 script 中补充：

```ts
function switchInterval(iv: 'd' | '1m') {
  if (barInterval.value === iv) return
  barInterval.value = iv
  barLimit.value = iv === '1m' ? 480 : 90
  void loadBars()
}
function switchBarLimit(n: number) {
  barLimit.value = n
  void loadBars()
}
function fmtAmount(v: number | null | undefined): string {
  if (v == null || Number.isNaN(v) || v <= 0) return '—'
  if (v >= 1e8) return (v / 1e8).toFixed(2) + '亿'
  if (v >= 1e4) return (v / 1e4).toFixed(1) + '万'
  return v.toFixed(0)
}
```

在 template 的 `.stock-body` 中补 `switchInterval`/`switchBarLimit` 调用的 handler 方法（已在 Step 4 script 定义）。

补充样式（追加到 style 末尾）：

```html
.quote-tab {
  display: grid;
  gap: 12px;
}
.quote-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 8px 12px;
  border: 1px solid var(--line);
  border-radius: 0.75rem;
  background: var(--surface-muted);
  padding: 12px;
}
.q-item {
  display: grid;
  gap: 2px;
}
.q-label {
  color: var(--muted);
  font-size: 0.72rem;
}
.q-value {
  font-size: 0.95rem;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}
.bar-controls {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}
.limits {
  display: flex;
  gap: 4px;
}
.chip {
  background: transparent;
  border: 1px solid var(--border);
  color: var(--muted);
  border-radius: 0.5rem;
  padding: 4px 8px;
  font-size: 0.75rem;
  cursor: pointer;
}
.chip.on {
  background: var(--brand-light);
  color: var(--brand);
  border-color: var(--brand-soft);
  font-weight: 500;
}
.chart :deep(.candle svg) {
  height: 340px;
}
.up {
  color: var(--danger);
}
.down {
  color: var(--ok);
}
.err {
  margin: 0;
  color: var(--danger);
  font-size: 0.85rem;
}
```

- [ ] **Step 5: 验证构建**

Run: `npm run build`
Expected: PASS

---

### Task 3: 基本面 tab

**Files:**
- Modify: `frontend/src/components/StockAnalysisModal.vue`

**Interfaces:**
- Consumes: `watchlistApi.fundamentals(vt)` → `Fundamentals`（已有类型）。
- Produces: `fundamental` tab 展示财报快照 + 披露日历。

- [ ] **Step 1: script 增加基本面状态**

追加：

```ts
const fund = ref<Fundamentals | null>(null)
const fundErr = ref('')
const fundLoading = ref(false)

async function loadFund() {
  if (!analysis.vtSymbol.value || analysis.isLoaded('fundamental')) return
  fundLoading.value = true
  fundErr.value = ''
  try {
    fund.value = await watchlistApi.fundamentals(analysis.vtSymbol.value)
    analysis.markLoaded('fundamental')
  } catch (e) {
    fundErr.value = e instanceof Error ? e.message : '基本面加载失败'
  } finally {
    fundLoading.value = false
  }
}
```

在 activeTab watch 中追加分支：

```ts
if (tab === 'fundamental' && analysis.vtSymbol.value && !analysis.isLoaded('fundamental'))
  void loadFund()
```

- [ ] **Step 2: template 基本面内容**

在 `stock-body` 内追加：

```html
<div v-if="analysis.activeTab.value === 'fundamental'" class="fund-tab">
  <p v-if="fundLoading" class="muted">加载基本面…</p>
  <p v-else-if="fundErr" class="err">{{ fundErr }}</p>
  <template v-else-if="fund">
    <section class="fund-block">
      <h4>财报</h4>
      <template v-if="fund.snapshot">
        <p class="muted">期末 {{ fmtYmd(fund.snapshot.end_date) }}
          <span v-if="fund.sync?.last_sync_at"> · 同步 {{ fund.sync.last_sync_at }}</span>
        </p>
        <dl class="fund-grid">
          <div><dt>营收</dt><dd class="mono">{{ fmtMoney(fund.snapshot.revenue) }}</dd></div>
          <div><dt>净利</dt><dd class="mono">{{ fmtMoney(fund.snapshot.net_income) }}</dd></div>
          <div><dt>营收同比</dt><dd>{{ fmtRatioPct(fund.snapshot.revenue_yoy) }}</dd></div>
          <div><dt>净利同比</dt><dd>{{ fmtRatioPct(fund.snapshot.net_income_yoy) }}</dd></div>
          <div><dt>ROE</dt><dd>{{ fmtRatioPct(fund.snapshot.roe) }}</dd></div>
          <div><dt>资产负债率</dt><dd>{{ fmtRatioPct(fund.snapshot.debt_ratio) }}</dd></div>
        </dl>
      </template>
      <p v-else class="muted">暂无财报，可去 Ops 同步自选财报。</p>
    </section>
    <section class="fund-block">
      <h4>披露</h4>
      <template v-if="fund.disclosures.length">
        <table class="fund-disc">
          <thead><tr><th>报告期</th><th>预告</th><th>公告</th><th>实际</th></tr></thead>
          <tbody>
            <tr v-for="d in fund.disclosures" :key="d.end_date">
              <td class="mono">{{ fmtYmd(d.end_date) }}</td>
              <td class="mono">{{ fmtYmd(d.pre_date) }}</td>
              <td class="mono">{{ fmtYmd(d.ann_date) }}</td>
              <td class="mono">{{ fmtYmd(d.actual_date) }}</td>
            </tr>
          </tbody>
        </table>
      </template>
      <p v-else class="muted">暂无披露日历。</p>
    </section>
  </template>
  <p v-else class="muted">无基本面数据</p>
</div>
```

- [ ] **Step 3: script 补辅助函数**

追加：

```ts
function fmtYmd(raw: string | null | undefined): string {
  const s = (raw || '').trim()
  if (!s) return '—'
  if (/^\d{8}$/.test(s)) return `${s.slice(0, 4)}-${s.slice(4, 6)}-${s.slice(6, 8)}`
  return s.slice(0, 10)
}
function fmtMoney(n: number | null | undefined): string {
  if (n == null || Number.isNaN(n)) return '—'
  if (Math.abs(n) >= 1e8) return `${(n / 1e8).toFixed(2)} 亿`
  if (Math.abs(n) >= 1e4) return `${(n / 1e4).toFixed(2)} 万`
  return n.toFixed(2)
}
function fmtRatioPct(n: number | null | undefined): string {
  if (n == null || Number.isNaN(n)) return '—'
  return `${(n * 100).toFixed(1)}%`
}
```

补充样式：

```html
.fund-block {
  display: grid;
  gap: 6px;
}
.fund-block h4 {
  margin: 0;
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--ink);
}
.fund-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 6px 16px;
  margin: 0;
}
.fund-grid dt {
  color: var(--muted);
  font-size: 0.75rem;
}
.fund-grid dd {
  margin: 0;
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--ink);
}
.fund-disc {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.8rem;
}
.fund-disc th,
.fund-disc td {
  padding: 5px 8px;
  border-bottom: 1px solid var(--line-soft);
  text-align: left;
}
.fund-disc th {
  color: var(--muted);
  font-weight: 500;
  background: var(--surface-muted);
}
```

- [ ] **Step 4: 验证构建**

Run: `npm run build`
Expected: PASS

---

### Task 4: 策略信号 tab

**Files:**
- Modify: `frontend/src/components/StockAnalysisModal.vue`

**Interfaces:**
- Consumes: `watchlistApi.strategyBoard({ signalMode })`、`BoardSignalMode`（来自 `src/lib/boardBacktestParams.ts`）。
- Produces: `signal` tab 展示该标的在三轨下的信号（表格：模式/信号/强度/摘要/参考买卖）。

- [ ] **Step 1: script 增加信号状态**

追加：

```ts
import type { BoardSignalMode } from '../lib/boardBacktestParams'
import type { StrategySignalRow } from '../api/watchlist'

const SIGNAL_MODES: { id: BoardSignalMode; label: string }[] = [
  { id: 'heuristic_v2', label: '启发式确认' },
  { id: 'double_ma', label: '回测双均线' },
  { id: 'trend_ma', label: '趋势均线' },
]
const signalRows = ref<{ mode: string; row: StrategySignalRow }[]>([])
const signalErr = ref('')
const signalLoading = ref(false)

async function loadSignals() {
  if (!analysis.vtSymbol.value || analysis.isLoaded('signal')) return
  signalLoading.value = true
  signalErr.value = ''
  try {
    const vt = analysis.vtSymbol.value
    const results = await Promise.all(
      SIGNAL_MODES.map(async (m) => {
        const board = await watchlistApi.strategyBoard({ signalMode: m.id })
        return { m, row: board.signals.find((s) => s.vt_symbol === vt) }
      }),
    )
    signalRows.value = results
      .filter((r): r is { m: { id: BoardSignalMode; label: string }; row: StrategySignalRow } => !!r.row)
      .map((r) => ({ mode: r.m.label, row: r.row }))
    analysis.markLoaded('signal')
  } catch (e) {
    signalErr.value = e instanceof Error ? e.message : '策略信号加载失败'
  } finally {
    signalLoading.value = false
  }
}
```

activeTab watch 追加：

```ts
if (tab === 'signal' && analysis.vtSymbol.value && !analysis.isLoaded('signal'))
  void loadSignals()
```

- [ ] **Step 2: template 信号内容**

在 `stock-body` 内追加：

```html
<div v-if="analysis.activeTab.value === 'signal'" class="signal-tab">
  <p v-if="signalLoading" class="muted">加载策略信号…</p>
  <p v-else-if="signalErr" class="err">{{ signalErr }}</p>
  <template v-else-if="signalRows.length">
    <div class="table-wrap">
      <table>
        <thead><tr><th>模式</th><th>信号</th><th>强度</th><th>参考买</th><th>参考卖</th><th>摘要</th></tr></thead>
        <tbody>
          <tr v-for="s in signalRows" :key="s.mode">
            <td>{{ s.mode }}</td>
            <td :class="signalClass(s.row.signal)">{{ s.row.signal_label }}</td>
            <td>
              <template v-if="s.row.strength_tier_label">
                {{ s.row.strength_tier_label }}<span v-if="s.row.strength != null"> · {{ s.row.strength.toFixed(1) }}</span>
              </template>
              <template v-else>{{ s.row.strength != null ? s.row.strength.toFixed(0) : '—' }}</template>
            </td>
            <td>{{ s.row.ref_buy_price != null ? s.row.ref_buy_price.toFixed(2) : '—' }}</td>
            <td>{{ s.row.ref_sell_price != null ? s.row.ref_sell_price.toFixed(2) : '—' }}</td>
            <td class="clip">{{ s.row.reason_summary || '—' }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </template>
  <p v-else class="muted">无信号，可去 Ops 跑 warm_watchlist_strategy_cache 预热。</p>
</div>
```

- [ ] **Step 3: script 补辅助函数**

追加：

```ts
function signalClass(sig: string) {
  if (sig === 'buy') return 'up'
  if (sig === 'sell') return 'down'
  return ''
}
```

补充样式：

```html
.table-wrap {
  border: 1px solid var(--line);
  border-radius: 0.75rem;
  overflow: auto;
  background: var(--surface);
  box-shadow: var(--shadow-card);
}
th,
td {
  padding: 8px 10px;
  border-bottom: 1px solid var(--border);
  font-size: 0.85rem;
  text-align: left;
  white-space: nowrap;
}
th {
  color: var(--muted);
  font-weight: 500;
  background: var(--surface-muted);
  position: sticky;
  top: 0;
}
.clip {
  max-width: 280px;
  overflow: hidden;
  text-overflow: ellipsis;
}
```

- [ ] **Step 4: 验证构建**

Run: `npm run build`
Expected: PASS

---

### Task 5: 雷达共振 tab

**Files:**
- Modify: `frontend/src/components/StockAnalysisModal.vue`

**Interfaces:**
- Consumes: `marketApi.radarResonance({ top_n, min_cards })`。
- Produces: `radar` tab 展示该标的的共振条目（共振分/卡片数/卡片标题/封板时间）。

- [ ] **Step 1: script 增加雷达状态**

追加：

```ts
import { marketApi } from '../api/market'

const radarEntry = ref<{
  card_count: number
  card_titles: string[]
  resonance_score: number
  seal_time_label?: string
} | null>(null)
const radarErr = ref('')
const radarLoading = ref(false)

async function loadRadar() {
  if (!analysis.vtSymbol.value || analysis.isLoaded('radar')) return
  radarLoading.value = true
  radarErr.value = ''
  try {
    const vt = analysis.vtSymbol.value
    const resp = await marketApi.radarResonance({ top_n: 100, min_cards: 1 })
    radarEntry.value = resp.entries.find((e) => e.vt_symbol === vt) || null
    analysis.markLoaded('radar')
  } catch (e) {
    radarErr.value = e instanceof Error ? e.message : '雷达共振加载失败'
  } finally {
    radarLoading.value = false
  }
}
```

activeTab watch 追加：

```ts
if (tab === 'radar' && analysis.vtSymbol.value && !analysis.isLoaded('radar'))
  void loadRadar()
```

- [ ] **Step 2: template 雷达内容**

在 `stock-body` 内追加：

```html
<div v-if="analysis.activeTab.value === 'radar'" class="radar-tab">
  <p v-if="radarLoading" class="muted">加载雷达共振…</p>
  <p v-else-if="radarErr" class="err">{{ radarErr }}</p>
  <template v-else-if="radarEntry">
    <div class="radar-summary">
      <div class="q-item"><span class="q-label">共振分</span><span class="q-value">{{ radarEntry.resonance_score.toFixed(1) }}</span></div>
      <div class="q-item"><span class="q-label">卡片数</span><span class="q-value">{{ radarEntry.card_count }}</span></div>
      <div class="q-item" v-if="radarEntry.seal_time_label"><span class="q-label">封板</span><span class="q-value">{{ radarEntry.seal_time_label }}</span></div>
    </div>
    <div v-if="radarEntry.card_titles.length" class="card-titles">
      <span v-for="t in radarEntry.card_titles" :key="t" class="chip-tag">{{ t }}</span>
    </div>
    <p v-else class="muted">暂无卡片标题</p>
  </template>
  <p v-else class="muted">暂无共振</p>
</div>
```

- [ ] **Step 3: 补充样式**

```html
.radar-summary {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 8px 12px;
  border: 1px solid var(--line);
  border-radius: 0.75rem;
  background: var(--surface-muted);
  padding: 12px;
}
.card-titles {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.chip-tag {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  border: 1px solid var(--border);
  border-radius: 0.5rem;
  padding: 2px 8px;
  font-size: 0.8rem;
  background: var(--bg);
}
```

- [ ] **Step 4: 验证构建**

Run: `npm run build`
Expected: PASS

---

### Task 6: AI 研报 tab

**Files:**
- Modify: `frontend/src/components/StockAnalysisModal.vue`

**Interfaces:**
- Consumes: `aiApi.streamTeam(vt, handlers, sessionId?, mode)`、`contentApi.teamReportsPage(vt, page, pageSize)`、`contentApi.teamReport(id)`、`aiApi.status()`、`MarkdownView`。
- Produces: `ai` tab 展示快速/深度模式切换 + 生成按钮 + 流式报告 + 历史报告列表/详情。

- [ ] **Step 1: script 增加 AI 状态**

追加：

```ts
import MarkdownView from './MarkdownView.vue'
import { aiApi } from '../api/ai'
import { contentApi, type TeamReportListItem, type TeamReport } from '../api/content'

const aiMode = ref<'fast' | 'deep'>('fast')
const aiBusy = ref(false)
const aiStatus = ref('')
const aiReport = ref('')
const aiErr = ref('')
const aiConfigured = ref(false)
const reportList = ref<TeamReportListItem[]>([])
const reportDetail = ref<TeamReport | null>(null)
const reportListErr = ref('')

async function checkAiStatus() {
  try {
    const st = await aiApi.status()
    aiConfigured.value = st.configured
  } catch {
    aiConfigured.value = false
  }
}

async function loadReportList() {
  if (!analysis.vtSymbol.value) return
  reportListErr.value = ''
  try {
    const page = await contentApi.teamReportsPage(analysis.vtSymbol.value, 1, 20)
    reportList.value = page.items
  } catch (e) {
    reportListErr.value = e instanceof Error ? e.message : '历史研报加载失败'
  }
}

async function openReport(id: number) {
  try {
    reportDetail.value = await contentApi.teamReport(id)
  } catch (e) {
    aiErr.value = e instanceof Error ? e.message : '研报详情加载失败'
  }
}

async function runAi() {
  const vt = analysis.vtSymbol.value
  if (!vt || aiBusy.value || !aiConfigured.value) return
  aiBusy.value = true
  aiErr.value = ''
  aiReport.value = ''
  aiStatus.value = aiMode.value === 'deep' ? '深度预取中…' : '预取中…'
  try {
    await aiApi.streamTeam(
      vt,
      {
        onEvent: (ev) => {
          if (ev.kind === 'started' && ev.agent && ev.agent !== 'system') {
            aiStatus.value = `${ev.label || ev.agent} 分析中…`
          }
          if (ev.kind === 'score' && ev.agent === 'system' && ev.weighted != null) {
            aiStatus.value =
              aiMode.value === 'deep'
                ? `加权 ${ev.weighted} · 三分析师并行中…`
                : `加权 ${ev.weighted} · 首席汇总中…`
          }
          if (ev.kind === 'delta' && ev.agent === 'chief' && ev.content) {
            aiStatus.value = '首席汇总中…'
            aiReport.value += ev.content
          }
          if (ev.kind === 'error') aiErr.value = ev.detail || '团队分析失败'
        },
        onReportSaved: () => {
          aiStatus.value = '研报已保存'
          void loadReportList()
        },
        onDone: () => {
          if (aiStatus.value) aiStatus.value = ''
        },
        onError: (err) => {
          aiErr.value = err
          aiStatus.value = ''
        },
      },
      undefined,
      aiMode.value,
    )
  } catch (e) {
    aiErr.value = e instanceof Error ? e.message : '团队分析失败'
  } finally {
    aiBusy.value = false
  }
}
```

activeTab watch 追加：

```ts
if (tab === 'ai' && analysis.vtSymbol.value && !analysis.isLoaded('ai')) {
  analysis.markLoaded('ai')
  void checkAiStatus()
  void loadReportList()
}
```

- [ ] **Step 2: template AI 内容**

在 `stock-body` 内追加：

```html
<div v-if="analysis.activeTab.value === 'ai'" class="ai-tab">
  <p v-if="aiConfigured === false" class="warn-banner">未配置 LLM_API_KEY，团队分析不可用。</p>
  <div class="ai-controls">
    <div class="team-mode">
      <label :class="{ on: aiMode === 'fast' }">
        <input v-model="aiMode" type="radio" value="fast" :disabled="aiBusy" />
        <span>快速</span>
      </label>
      <label :class="{ on: aiMode === 'deep' }">
        <input v-model="aiMode" type="radio" value="deep" :disabled="aiBusy" />
        <span>深度</span>
      </label>
    </div>
    <button type="button" class="primary" :disabled="aiBusy || !aiConfigured" @click="runAi">
      {{ aiBusy ? '分析中…' : aiMode === 'deep' ? '深度团队分析' : '团队分析' }}
    </button>
  </div>
  <p v-if="aiStatus" class="muted">{{ aiStatus }}</p>
  <p v-if="aiErr" class="err">{{ aiErr }}</p>
  <div v-if="aiReport" class="report-body">
    <MarkdownView :source="aiReport" />
  </div>

  <section class="report-section">
    <h4>历史研报</h4>
    <p v-if="reportListErr" class="err">{{ reportListErr }}</p>
    <div v-else-if="reportList.length" class="report-list">
      <button
        v-for="r in reportList"
        :key="r.id"
        type="button"
        class="report-item"
        :class="{ on: reportDetail?.id === r.id }"
        @click="openReport(r.id)"
      >
        <span class="report-title">{{ r.title }}</span>
        <span class="muted tiny">{{ r.mode }} · {{ r.created_at }}</span>
      </button>
    </div>
    <p v-else class="muted">暂无历史研报，可点击上方生成。</p>
    <div v-if="reportDetail" class="report-detail">
      <h5>{{ reportDetail.title }}</h5>
      <MarkdownView :source="reportDetail.body" />
    </div>
  </section>
</div>
```

- [ ] **Step 3: 补充样式**

```html
.ai-controls {
  display: flex;
  gap: 10px;
  align-items: center;
  flex-wrap: wrap;
}
.team-mode {
  display: inline-flex;
  gap: 8px;
}
.team-mode label {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 0.82rem;
  color: var(--muted);
}
.team-mode label.on {
  color: var(--brand);
  font-weight: 500;
}
.primary {
  background: var(--accent);
  color: var(--brand-foreground);
  border: none;
  border-radius: 0.5rem;
  padding: 8px 12px;
  font-weight: 600;
  cursor: pointer;
}
.primary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.warn-banner {
  margin: 0;
  padding: 8px 10px;
  border: 1px solid var(--line);
  border-radius: 0.5rem;
  background: var(--surface-muted);
  color: var(--danger);
  font-size: 0.82rem;
}
.report-section {
  display: grid;
  gap: 8px;
}
.report-section h4 {
  margin: 0;
  font-size: 0.9rem;
}
.report-list {
  display: grid;
  gap: 4px;
}
.report-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  background: var(--surface-muted);
  border: 1px solid var(--border);
  border-radius: 0.5rem;
  padding: 6px 10px;
  text-align: left;
  cursor: pointer;
  color: var(--text);
  font-size: 0.82rem;
}
.report-item:hover,
.report-item.on {
  border-color: var(--brand-soft);
  background: var(--brand-light);
  color: var(--brand);
}
.report-title {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.report-detail {
  border: 1px solid var(--line);
  border-radius: 0.75rem;
  padding: 12px 14px;
  background: var(--surface-muted);
}
.report-detail h5 {
  margin: 0 0 8px;
  font-size: 0.9rem;
}
.report-body :deep(.markdown) {
  font-size: 0.82rem;
  line-height: 1.5;
}
.report-detail :deep(.markdown) {
  font-size: 0.82rem;
  line-height: 1.5;
}
.tiny {
  font-size: 0.72rem;
}
```

- [ ] **Step 4: 验证构建**

Run: `npm run build`
Expected: PASS

---

### Task 7: 笔记 tab

**Files:**
- Modify: `frontend/src/components/StockAnalysisModal.vue`

**Interfaces:**
- Consumes: `contentApi.memo(vt)`、`saveMemo(vt, body)`、`entriesPage(vt, page, pageSize)`、`addEntry(vt, body)`、`deleteEntry(id)`。
- Produces: `notes` tab 展示速记编辑 + 条目列表/新增/删除。

- [ ] **Step 1: script 增加笔记状态**

追加：

```ts
const memo = ref<NoteMemo | null>(null)
const memoDraft = ref('')
const memoSaving = ref(false)
const memoErr = ref('')
const entries = ref<NoteEntry[]>([])
const entryDraft = ref('')
const entryErr = ref('')
const notesLoaded = ref(false)

async function loadNotes() {
  if (!analysis.vtSymbol.value || notesLoaded.value) return
  notesLoaded.value = true
  try {
    const vt = analysis.vtSymbol.value
    const [m, page] = await Promise.all([
      contentApi.memo(vt),
      contentApi.entriesPage(vt, 1, 50),
    ])
    memo.value = m
    memoDraft.value = m.body || ''
    entries.value = page.items
  } catch (e) {
    memoErr.value = e instanceof Error ? e.message : '笔记加载失败'
  }
}

async function saveMemo() {
  if (!analysis.vtSymbol.value || memoSaving.value) return
  memoSaving.value = true
  memoErr.value = ''
  try {
    memo.value = await contentApi.saveMemo(analysis.vtSymbol.value, memoDraft.value.trim())
  } catch (e) {
    memoErr.value = e instanceof Error ? e.message : '速记保存失败'
  } finally {
    memoSaving.value = false
  }
}

async function addEntry() {
  const body = entryDraft.value.trim()
  if (!analysis.vtSymbol.value || !body) return
  entryErr.value = ''
  try {
    await contentApi.addEntry(analysis.vtSymbol.value, body)
    entryDraft.value = ''
    const page = await contentApi.entriesPage(analysis.vtSymbol.value, 1, 50)
    entries.value = page.items
  } catch (e) {
    entryErr.value = e instanceof Error ? e.message : '添加失败'
  }
}

async function removeEntry(id: number) {
  try {
    await contentApi.deleteEntry(id)
    entries.value = entries.value.filter((e) => e.id !== id)
  } catch (e) {
    entryErr.value = e instanceof Error ? e.message : '删除失败'
  }
}
```

activeTab watch 追加：

```ts
if (tab === 'notes' && analysis.vtSymbol.value && !notesLoaded.value) void loadNotes()
```

- [ ] **Step 2: template 笔记内容**

在 `stock-body` 内追加：

```html
<div v-if="analysis.activeTab.value === 'notes'" class="notes-tab">
  <section class="memo-panel">
    <h4>速记</h4>
    <textarea v-model="memoDraft" rows="3" placeholder="记录该标的要点…"></textarea>
    <button type="button" class="primary" :disabled="memoSaving" @click="saveMemo">
      {{ memoSaving ? '保存中…' : '保存速记' }}
    </button>
    <p v-if="memoErr" class="err">{{ memoErr }}</p>
  </section>
  <section class="entry-panel">
    <h4>流水</h4>
    <div class="entry-add">
      <input v-model="entryDraft" placeholder="追加一条流水" @keyup.enter="addEntry" />
      <button type="button" class="ghost" @click="addEntry">添加</button>
    </div>
    <p v-if="entryErr" class="err">{{ entryErr }}</p>
    <div v-if="entries.length" class="entry-list">
      <div v-for="e in entries" :key="e.id" class="entry">
        <div class="entry-body">{{ e.body }}</div>
        <div class="entry-foot">
          <span class="muted tiny">{{ e.created_at }}</span>
          <button type="button" class="link" @click="removeEntry(e.id)">删</button>
        </div>
      </div>
    </div>
    <p v-else class="muted">暂无流水。</p>
  </section>
</div>
```

- [ ] **Step 3: 补充样式**

```html
.notes-tab {
  display: grid;
  gap: 12px;
}
.memo-panel,
.entry-panel {
  display: grid;
  gap: 8px;
}
.memo-panel h4,
.entry-panel h4 {
  margin: 0;
  font-size: 0.9rem;
}
.memo-panel textarea {
  width: 100%;
  border: 1px solid var(--border);
  border-radius: 0.5rem;
  background: var(--bg-elevated);
  color: var(--text);
  padding: 8px 10px;
  resize: vertical;
  font-family: inherit;
  font-size: 0.85rem;
}
.entry-add {
  display: flex;
  gap: 8px;
}
.entry-add input {
  flex: 1;
  border: 1px solid var(--border);
  border-radius: 0.5rem;
  background: var(--bg-elevated);
  color: var(--text);
  padding: 8px 10px;
}
.ghost {
  background: transparent;
  border: 1px solid var(--border);
  color: var(--text);
  border-radius: 0.5rem;
  padding: 6px 10px;
  cursor: pointer;
}
.ghost:hover {
  background: var(--brand-light);
  color: var(--brand);
  border-color: var(--brand-soft);
}
.entry-list {
  display: grid;
  gap: 4px;
}
.entry {
  border: 1px solid var(--border);
  border-radius: 0.5rem;
  padding: 6px 10px;
  background: var(--surface-muted);
  display: grid;
  gap: 4px;
}
.entry-body {
  font-size: 0.85rem;
}
.entry-foot {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.link {
  background: none;
  border: none;
  color: var(--muted);
  padding: 0;
  cursor: pointer;
}
.link:hover {
  color: var(--danger);
}
```

- [ ] **Step 4: 验证构建**

Run: `npm run build`
Expected: PASS

---

### Task 8: 五个页面接入点

**Files:**
- Modify: `frontend/src/views/MarketView.vue`
- Modify: `frontend/src/views/WatchlistView.vue`
- Modify: `frontend/src/views/BoardView.vue`
- Modify: `frontend/src/views/StrategyView.vue`
- Modify: `frontend/src/views/RadarView.vue`

**Interfaces:**
- Consumes: `useStockAnalysis()`、`<StockAnalysisModal />`。
- Produces: 各页面代码处可点「分析」打开弹窗。

- [ ] **Step 1: MarketView 接入**

`frontend/src/views/MarketView.vue`：

1. import 追加：

```ts
import StockAnalysisModal from '../components/StockAnalysisModal.vue'
import { useStockAnalysis } from '../composables/useStockAnalysis'

const analysis = useStockAnalysis()
```

2. `row-ops` 操作区（K线/自选/基本面按钮旁）加「分析」icon 按钮：

```html
<button type="button" class="icon-btn" title="分析" @click.stop="analysis.open(r.vt_symbol, r.name)">
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"
    stroke-linecap="round" stroke-linejoin="round">
    <path d="M8.25 21v-4.875c0-.621.504-1.125 1.125-1.125h5.25c.621 0 1.125.504 1.125 1.125V21m0 0h4.5M3.75 21h4.5M3.75 21V9m0 0l-1.5 3M3.75 9l9-6 9 6m-13.5 0v6h4.5v-6" />
  </svg>
</button>
```

3. 页面末尾 `</AppShell>` 前挂载：

```html
<StockAnalysisModal />
```

- [ ] **Step 2: WatchlistView 接入**

`frontend/src/views/WatchlistView.vue`：

1. import 追加：

```ts
import StockAnalysisModal from '../components/StockAnalysisModal.vue'
import { useStockAnalysis } from '../composables/useStockAnalysis'

const analysis = useStockAnalysis()
```

2. 行内「删」按钮前加：

```html
<button type="button" class="link" @click.stop="analysis.open(item.vt_symbol, item.name)">析</button>
```

3. `</AppShell>` 前挂载 `<StockAnalysisModal />`。

- [ ] **Step 3: BoardView 接入**

`frontend/src/views/BoardView.vue`：

1. import 追加：

```ts
import StockAnalysisModal from '../components/StockAnalysisModal.vue'
import { useStockAnalysis } from '../composables/useStockAnalysis'

const analysis = useStockAnalysis()
```

2. 信号区每行「入名单/移出」按钮前加：

```html
<button type="button" class="link" @click.stop="analysis.open(row.vt_symbol, row.name)">析</button>
```

3. 持仓区每行「改/删」前加：

```html
<button type="button" class="link" @click.stop="analysis.open(row.vt_symbol, row.name)">析</button>
```

4. `</AppShell>` 前挂载 `<StockAnalysisModal />`。

- [ ] **Step 4: StrategyView 接入**

`frontend/src/views/StrategyView.vue`：

1. import 追加：

```ts
import StockAnalysisModal from '../components/StockAnalysisModal.vue'
import { useStockAnalysis } from '../composables/useStockAnalysis'

const analysis = useStockAnalysis()
```

2. 信号明细行代码按钮旁加：

```html
<button type="button" class="link" @click="analysis.open(row.vt_symbol, row.name)">析</button>
```

3. `</AppShell>` 前挂载 `<StockAnalysisModal />`。

- [ ] **Step 5: RadarView 接入**

`frontend/src/views/RadarView.vue`：

1. import 追加：

```ts
import StockAnalysisModal from '../components/StockAnalysisModal.vue'
import { useStockAnalysis } from '../composables/useStockAnalysis'

const analysis = useStockAnalysis()
```

2. 共振区 `side-row` 内（加自选按钮旁）加：

```html
<button type="button" class="link" @click="analysis.open(e.vt_symbol, e.name)">析</button>
```

3. horizon/predict 表格行内（若有操作列）加「析」按钮。
4. `</AppShell>` 前挂载 `<StockAnalysisModal />`。

- [ ] **Step 6: 验证构建**

Run: `npm run build`
Expected: PASS

---

### Task 9: 整体验证与 lint

**Files:**
- 校验 Task 1-8 改动的全部文件。

- [ ] **Step 1: 全量构建**

Run: `npm run build`
Expected: PASS

- [ ] **Step 2: lint 检查**

Run: `npm run lint:check`
Expected: 新增/改动文件无 eslint 报错。

- [ ] **Step 3: 手动冒烟验证**

启动 `npm run dev`，在浏览器验证：

1. 市场页表格点「分析」icon → 弹窗打开，默认行情 tab 显示摘要 + K 线，日K/1分K 切换正常
2. 自选/看板/策略总览/雷达页「析」按钮均能打开弹窗
3. 切换基本面/策略信号/雷达/AI研报/笔记 tab，各自懒加载成功；无数据时显示提示
4. AI 研报快速/深度可生成，流式输出；历史报告可查看详情
5. 笔记速记保存、条目增删可用
6. Esc/遮罩关闭弹窗正常
7. 打开第二个标的，数据刷新为新标的（loadedTabs 已重置）

- [ ] **Step 4: 提交确认**

向用户确认后再提交，commit message 示例：

```
feat(ui): 新增个股分析全局弹窗

六tab聚合行情/基本面/策略信号/雷达/AI研报/笔记，五个页面统一接入。
```

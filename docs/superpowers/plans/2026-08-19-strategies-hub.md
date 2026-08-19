# 策略总览页 + 全局「策略」入口 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在全局侧边栏「交易」组新增「策略」入口，落地 `/strategies` 总览页，集中展示三种信号模式状态、回测策略清单与信号明细。

**Architecture:** 纯前端改动。新增 `StrategyView.vue` 复用现有 `watchlistApi.strategyBoard({ signalMode })` 与 `backtestApi.strategies()`；`AppShell.vue`/`NavIcon.vue`/`router/index.ts` 增加导航与路由；`BoardView.vue` 支持读取 `signal_mode` query 实现跳转联动。无后端改动。

**Tech Stack:** Vue 3 `<script setup lang="ts">`、vue-router、Vite、TypeScript。验证用 `npm run build`（vue-tsc + vite）与 `npm run lint:check`（无前端测试框架）。

## Global Constraints

- 前端源码在 `frontend/`，命令均在 `frontend/` 下执行。
- 复用现有类型，不新建重复类型：`BoardSignalMode`（`src/lib/boardBacktestParams.ts`）、`StrategyBoard`/`StrategySignalRow`（`src/api/watchlist.ts`）、`StrategyInfo`（`src/api/backtest.ts`）。
- 「看板」跳转 query 键为 `signal_mode`；与 `BoardView.vue` 既有 `SIGNAL_MODE_KEY` 的 localStorage 值保持一致。
- 图标沿用 Heroicons 风格 stroke（`NavIcon.vue` 现有写法）。
- 提交前需经用户确认；commit message 用简体中文，格式 `<type>(<scope>): <简述>`。

---

### Task 1: 导航与路由

**Files:**
- Modify: `frontend/src/components/NavIcon.vue`
- Modify: `frontend/src/components/AppShell.vue`
- Modify: `frontend/src/router/index.ts`

**Interfaces:**
- Produces: `NavIcon` 支持 `name="strategies"`；`AppShell` 的 `active` prop 支持 `'strategies'`；路由 `/strategies` → `StrategyView.vue`（Task 3 创建）。

- [ ] **Step 1: NavIcon.vue 增加 `strategies` 图标**

在 `frontend/src/components/NavIcon.vue` 中：

1. `NavIconName` 联合类型末尾追加 `| 'strategies'`。
2. `paths` 对象末尾追加：

```ts
  strategies: [
    'M10.5 6h9.75M10.5 6a1.5 1.5 0 11-3 0m3 0a1.5 1.5 0 10-3 0M3.75 6H7.5m3 12h9.75m-9.75 0a1.5 1.5 0 01-3 0m3 0a1.5 1.5 0 00-3 0m-3.75 0H7.5m9-6h3.75m-3.75 0a1.5 1.5 0 01-3 0m3 0a1.5 1.5 0 00-3 0m-9.75 0h9.75',
  ],
```

- [ ] **Step 2: AppShell.vue 加入导航项**

在 `frontend/src/components/AppShell.vue` 中：

1. `active` 联合类型末尾追加 `| 'strategies'`。
2. `NavKey` 联合类型末尾追加 `| 'strategies'`。
3. `navGroups`「交易」组内 `board` 项之后插入：

```ts
      { key: 'strategies', label: '策略', to: '/strategies', enabled: true },
```

- [ ] **Step 3: router/index.ts 注册路由**

在 `frontend/src/router/index.ts` 中 `board` 路由之后追加：

```ts
    {
      path: '/strategies',
      name: 'strategies',
      component: () => import('../views/StrategyView.vue'),
    },
```

- [ ] **Step 4: 验证构建**

Run: `npm run build`
Expected: PASS（vue-tsc 无类型错误；此时 `StrategyView.vue` 尚不存在，动态 import 在运行时才解析，不阻塞构建）

---

### Task 2: BoardView 支持 `signal_mode` query 联动

**Files:**
- Modify: `frontend/src/views/BoardView.vue`

**Interfaces:**
- Consumes: Task 1 的路由 `signal_mode` 约定。
- Produces: `/board?signal_mode=<mode>` 进入时，`signalMode` 覆盖 localStorage 并高亮。

- [ ] **Step 1: 引入 useRoute**

在 `frontend/src/views/BoardView.vue` 顶部，`import { useRouter } from 'vue-router'` 改为：

```ts
import { useRoute, useRouter } from 'vue-router'
```

在 `const router = useRouter()` 之后追加：

```ts
const route = useRoute()
```

- [ ] **Step 2: onMounted 读取 query 覆盖模式**

将现有 `onMounted`（当前为 `onMounted(async () => { await refreshBoard() ... })`）改为：

```ts
onMounted(async () => {
  const sm = typeof route.query.signal_mode === 'string' ? route.query.signal_mode : ''
  if ((VALID_SIGNAL_MODES as string[]).includes(sm)) {
    signalMode.value = sm as SignalMode
    saveSignalMode(sm)
  }
  await refreshBoard()
  boardTimer = window.setInterval(tickBoard, 45000)
})
```

- [ ] **Step 3: 验证构建**

Run: `npm run build`
Expected: PASS

---

### Task 3: StrategyView 策略总览页

**Files:**
- Create: `frontend/src/views/StrategyView.vue`

**Interfaces:**
- Consumes:
  - `watchlistApi.strategyBoard(opts: { signalMode?: string })` → `Promise<StrategyBoard>`
  - `backtestApi.strategies()` → `Promise<StrategyInfo[]>`
  - `useQuoteNotify(handlers)` → `{ connected, pollIntervalMs }`
  - `buildAlignedBacktestQuery(mode: BoardSignalMode, vt: string, configKey: string)` → `Record<string, string>`
- Produces: `/strategies` 页面，顶部三张信号模式卡 + 中部回测策略卡 + 底部信号明细表。

- [ ] **Step 1: 创建 script 部分**

创建 `frontend/src/views/StrategyView.vue`，script 内容：

```vue
<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import AppShell from '../components/AppShell.vue'
import { backtestApi, type StrategyInfo } from '../api/backtest'
import { watchlistApi, type StrategyBoard } from '../api/watchlist'
import { POLL_SLOW_MS, useQuoteNotify } from '../composables/useQuoteNotify'
import {
  buildAlignedBacktestQuery,
  type BoardSignalMode,
} from '../lib/boardBacktestParams'

const SIGNAL_MODES: { id: BoardSignalMode; label: string }[] = [
  { id: 'heuristic_v2', label: '启发式确认' },
  { id: 'double_ma', label: '回测双均线' },
  { id: 'trend_ma', label: '趋势均线' },
]

const router = useRouter()

const boards = ref<Partial<Record<BoardSignalMode, StrategyBoard>>>({})
const boardErrors = ref<Partial<Record<BoardSignalMode, string>>>({})
const strategies = ref<StrategyInfo[]>([])
const strategiesError = ref('')
const loading = ref(false)
const autoRefresh = ref(true)
const activeMode = ref<BoardSignalMode>('heuristic_v2')

const { connected } = useQuoteNotify({
  onQuotesUpdated: () => {
    if (!autoRefresh.value || document.hidden) return
    void load(true)
  },
})

const refreshLabel = computed(() => {
  if (!autoRefresh.value) return '已暂停自动刷新'
  return connected.value ? 'WS + 慢轮询' : '15 秒刷新'
})

const boardList = computed(() =>
  SIGNAL_MODES.map((m) => ({
    ...m,
    board: boards.value[m.id] || null,
    error: boardErrors.value[m.id] || '',
  })),
)

const activeBoard = computed(() => boards.value[activeMode.value] || null)
const activeError = computed(() => boardErrors.value[activeMode.value] || '')

let timer: number | undefined

function pollIntervalMs(): number {
  return connected.value ? POLL_SLOW_MS : 15_000
}

function restartPoll() {
  if (timer) window.clearInterval(timer)
  timer = window.setInterval(() => {
    if (!autoRefresh.value || document.hidden) return
    void load(true)
  }, pollIntervalMs())
}

watch(connected, () => restartPoll())

async function load(quiet = false) {
  if (!quiet) loading.value = true
  try {
    await Promise.all(
      SIGNAL_MODES.map(async (m) => {
        try {
          boards.value[m.id] = await watchlistApi.strategyBoard({ signalMode: m.id })
          boardErrors.value[m.id] = ''
        } catch (e) {
          boardErrors.value[m.id] = e instanceof Error ? e.message : '加载失败'
        }
      }),
    )
    if (!strategies.value.length && !strategiesError.value) {
      try {
        strategies.value = await backtestApi.strategies()
      } catch (e) {
        strategiesError.value = e instanceof Error ? e.message : '回测策略加载失败'
      }
    }
  } finally {
    loading.value = false
  }
}

function gotoBoard(mode: BoardSignalMode) {
  void router.push({ path: '/board', query: { signal_mode: mode } })
}

function gotoBacktest(mode: BoardSignalMode) {
  const board = boards.value[mode]
  const vt = board?.signals?.[0]?.vt_symbol || ''
  if (!vt) return
  void router.push({
    path: '/backtest',
    query: buildAlignedBacktestQuery(mode, vt, board?.config_key || ''),
  })
}

function gotoBacktestStrategy(strategyId: string) {
  void router.push({ path: '/backtest', query: { strategy: strategyId } })
}

function gotoWatchlist(vt: string) {
  if (!vt) return
  void router.push({ path: '/watchlist', query: { symbol: vt } })
}

function fmtPct(v: number | null | undefined): string {
  if (v == null || Number.isNaN(v)) return '—'
  return `${(v * 100).toFixed(1)}%`
}

function fmtYmd(raw: string | null | undefined): string {
  const s = (raw || '').trim()
  if (!s) return '—'
  if (/^\d{8}$/.test(s)) return `${s.slice(0, 4)}-${s.slice(4, 6)}-${s.slice(6, 8)}`
  return s.slice(0, 10)
}

function signalClass(sig: string) {
  if (sig === 'buy') return 'up'
  if (sig === 'sell') return 'down'
  return ''
}

onMounted(() => {
  void load()
  restartPoll()
})

onUnmounted(() => {
  if (timer) window.clearInterval(timer)
})
</script>
```

- [ ] **Step 2: 创建 template 部分**

在同文件 `</script>` 之后追加：

```html
<template>
  <AppShell title="策略" subtitle="策略信号总览 · 回测策略清单" active="strategies">
    <div class="page">
      <div class="toolbar">
        <p class="muted hint">
          三轨信号缓存（启发式 / 双均线 / 趋势均线）；无数据时可去 Ops 跑
          <code>warm_watchlist_strategy_cache</code> 预热。
          <RouterLink to="/ops" class="draft-link">去 Ops</RouterLink>
        </p>
        <div class="actions">
          <label class="auto">
            <input v-model="autoRefresh" type="checkbox" />
            {{ refreshLabel }}
          </label>
          <button class="ghost" type="button" :disabled="loading" @click="load()">刷新</button>
        </div>
      </div>

      <section class="cards">
        <div v-for="m in boardList" :key="m.id" class="card" :class="{ on: activeMode === m.id }">
          <div class="k">{{ m.label }}</div>
          <template v-if="m.board">
            <div class="v">{{ m.board.signals.length }} 条信号</div>
            <div class="s mono muted">{{ m.board.config_key }}</div>
            <div class="s muted">来源 {{ m.board.source }} · as_of {{ fmtYmd(m.board.as_of) }}</div>
            <div class="s muted">
              仓位建议 {{ fmtPct(m.board.risk_summary?.actual_position_pct) }}
            </div>
            <div class="card-actions">
              <button type="button" class="ghost tiny-btn" @click="gotoBoard(m.id)">去看板</button>
              <button
                type="button"
                class="ghost tiny-btn"
                :disabled="!m.board.signals.length"
                @click="gotoBacktest(m.id)"
              >
                同参回测
              </button>
            </div>
          </template>
          <div v-else-if="m.error" class="s err">{{ m.error }}</div>
          <div v-else class="s muted">加载中…</div>
        </div>
      </section>

      <section class="card">
        <h3>回测策略</h3>
        <p v-if="strategiesError" class="err">{{ strategiesError }}</p>
        <div v-else-if="strategies.length" class="bt-grid">
          <div v-for="s in strategies" :key="s.id" class="bt-card">
            <div class="k">{{ s.name }}</div>
            <p class="s muted">{{ s.description }}</p>
            <p class="s mono muted">interval {{ s.interval }} · {{ s.engine }}</p>
            <div class="card-actions">
              <button type="button" class="ghost tiny-btn" @click="gotoBacktestStrategy(s.id)">
                去回测
              </button>
            </div>
          </div>
        </div>
        <p v-else class="s muted">加载中…</p>
      </section>

      <section class="card">
        <h3>
          信号明细
          <span v-if="activeBoard" class="muted">{{ activeBoard.signals.length }}</span>
        </h3>
        <div class="mode-tabs">
          <button
            v-for="m in SIGNAL_MODES"
            :key="m.id"
            type="button"
            class="ghost"
            :class="{ on: activeMode === m.id }"
            @click="activeMode = m.id"
          >
            {{ m.label }}
          </button>
        </div>
        <p v-if="activeError" class="err">{{ activeError }}</p>
        <div v-else-if="activeBoard" class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>代码</th>
                <th>名称</th>
                <th>现价</th>
                <th>信号</th>
                <th>强度</th>
                <th>摘要</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in activeBoard.signals" :key="row.vt_symbol">
                <td class="mono">
                  <button type="button" class="chip-link" @click="gotoWatchlist(row.vt_symbol)">
                    {{ row.vt_symbol }}
                  </button>
                </td>
                <td>{{ row.name || '—' }}</td>
                <td>{{ row.last_price != null ? row.last_price.toFixed(2) : '—' }}</td>
                <td :class="signalClass(row.signal)">{{ row.signal_label }}</td>
                <td>
                  <template v-if="row.strength_tier_label">
                    {{ row.strength_tier_label
                    }}<span v-if="row.strength != null"> · {{ row.strength.toFixed(1) }}</span>
                  </template>
                  <template v-else>
                    {{ row.strength != null ? row.strength.toFixed(0) : '—' }}
                  </template>
                </td>
                <td class="clip">{{ row.reason_summary || '—' }}</td>
              </tr>
              <tr v-if="!activeBoard.signals.length">
                <td colspan="6" class="empty">无信号（可去 Ops 跑 warm_watchlist_strategy_cache 预热）</td>
              </tr>
            </tbody>
          </table>
        </div>
        <p v-else class="s muted">加载中…</p>
      </section>
    </div>
  </AppShell>
</template>
```

- [ ] **Step 3: 创建样式部分**

在同文件 template 之后追加：

```html
<style scoped>
.page {
  display: grid;
  gap: 14px;
}
.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}
.hint {
  margin: 0;
  font-size: 0.8rem;
  max-width: 56ch;
}
.actions {
  display: flex;
  gap: 8px;
  align-items: center;
}
.auto {
  display: flex;
  gap: 6px;
  align-items: center;
  color: var(--muted);
  font-size: 0.8rem;
}
.cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 10px;
}
.card {
  border: 1px solid var(--line);
  border-radius: 0.75rem;
  background: var(--surface);
  box-shadow: var(--shadow-card);
  padding: 14px 16px;
  display: grid;
  gap: 2px;
  align-content: start;
}
.card.on {
  border-color: var(--brand-soft);
  background: linear-gradient(180deg, #fffdfb 0%, var(--surface) 100%);
}
.card h3 {
  margin: 0 0 10px;
  font-size: 0.9rem;
  font-weight: 600;
}
.k {
  color: var(--muted);
  font-size: 0.78rem;
  font-weight: 500;
  letter-spacing: 0.02em;
}
.v {
  margin-top: 4px;
  font-size: 1.1rem;
  font-weight: 600;
}
.s {
  margin-top: 4px;
  font-size: 0.8rem;
}
.card-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 8px;
}
.ghost {
  background: transparent;
  border: 1px solid var(--border);
  color: var(--text);
  border-radius: 0.5rem;
  padding: 6px 10px;
  cursor: pointer;
}
.ghost:hover:not(:disabled) {
  background: var(--brand-light);
  color: var(--brand);
  border-color: var(--brand-soft);
}
.ghost:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.ghost.on {
  background: var(--brand-light);
  color: var(--brand);
  border-color: var(--brand-soft);
  font-weight: 500;
}
.tiny-btn {
  padding: 4px 8px;
  font-size: 0.8rem;
}
.mode-tabs {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  margin-bottom: 10px;
}
.bt-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 10px;
}
.bt-card {
  border: 1px solid var(--line);
  border-radius: 0.75rem;
  background: var(--surface-muted);
  padding: 12px 14px;
  display: grid;
  gap: 2px;
  align-content: start;
}
.table-wrap {
  border: 1px solid var(--line);
  border-radius: 0.75rem;
  overflow: auto;
  background: var(--surface);
  box-shadow: var(--shadow-card);
  max-height: 70vh;
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
tbody tr:hover td {
  background: var(--surface-muted);
}
.clip {
  max-width: 280px;
  overflow: hidden;
  text-overflow: ellipsis;
}
.chip-link {
  background: none;
  border: none;
  color: var(--text);
  font-family: var(--mono);
  padding: 0;
  cursor: pointer;
}
.chip-link:hover {
  color: var(--brand);
}
.mono {
  font-family: var(--mono);
}
.up {
  color: var(--danger);
}
.down {
  color: var(--ok);
}
.empty {
  text-align: center;
  color: var(--muted);
  padding: 28px !important;
}
.muted {
  color: var(--muted);
}
.err {
  margin: 0;
  color: var(--danger);
  font-size: 0.85rem;
}
.draft-link {
  color: var(--brand);
  margin-left: 4px;
}
</style>
```

- [ ] **Step 4: 验证构建**

Run: `npm run build`
Expected: PASS（`active="strategies"` 与 AppShell 类型、`BoardSignalMode` 导入均通过类型检查）

---

### Task 4: 整体验证与 lint

**Files:**
- 校验 Task 1-3 改动的全部文件。

- [ ] **Step 1: 全量构建**

Run: `npm run build`
Expected: PASS

- [ ] **Step 2: lint 检查新增/改动文件**

Run: `npm run lint:check`
Expected: 新增文件（`StrategyView.vue`、`NavIcon.vue`、`AppShell.vue`、`BoardView.vue`、`router/index.ts`）无 eslint 报错；若存在改动前已存在的报错，仅需确认未新增。

- [ ] **Step 3: 手动冒烟验证**

启动 `npm run dev`，在浏览器验证：

1. 侧边栏「交易」组「看板」之后出现「策略」入口，图标正常。
2. `/strategies` 加载：三张信号模式卡（有缓存时显示信号数/来源/as_of/仓位建议；无缓存显示提示）、回测策略两卡、底部信号明细默认启发式。
3. 点击「去看板」→ `/board?signal_mode=double_ma`，看板页模式 tab 高亮为「回测双均线」。
4. 信号明细 tab 切换三种模式，表格数据随之变化；点击代码跳转 `/watchlist?symbol=<vt>`。
5. 「刷新」按钮与自动刷新正常，刷新标签随 WS 连接状态变化。

- [ ] **Step 4: 提交确认**

向用户确认后再提交，commit message 示例：

```
feat(ui): 新增策略总览页与侧边栏策略入口

集中展示三种信号模式与回测策略清单，支持一键跳转看板/回测。
```

<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import type { RankRow } from '../../../api/market'
import { formatAmountYi, formatNum2, formatPrice } from '../../../lib/format'
import { cmpNullable } from '../../../lib/sort'

const field = defineModel<string>('field', { required: true })
const rankLimit = defineModel<number>('rankLimit', { required: true })
const autoRefresh = defineModel<boolean>('autoRefresh', { required: true })

const props = defineProps<{
  ranks: RankRow[]
  loading: boolean
  error: string
  refreshLabel: string
  watchSet: Set<string>
}>()

const emit = defineEmits<{
  refresh: []
  'toggle-watch': [row: RankRow]
  chart: [vt: string]
  fund: [vt: string]
  analyze: [vt: string, name: string]
  'search-active': [active: boolean]
}>()

const rankLimitChoices = [50, 100, 200, 500, 0]

function rankLimitLabel(n: number): string {
  return n === 0 ? '全部' : String(n)
}

const fields = [
  { id: 'change_pct', label: '涨幅', col: '涨幅%' },
  { id: 'turnover_rate', label: '换手', col: '换手%' },
  { id: 'amount', label: '成交额', col: '成交额' },
  { id: 'volume_ratio', label: '量比', col: '量比' },
]

const fieldMeta = computed(() => fields.find((f) => f.id === field.value) || fields[0])

type SortKey =
  | 'last_price'
  | 'change_pct'
  | 'change_amount'
  | 'turnover_rate'
  | 'amount'
  | 'volume_ratio'
  | 'amplitude'
  | 'total_mv'
  | null

const listFilter = ref('')
const sortKey = ref<SortKey>(null)
const sortDir = ref<'asc' | 'desc'>('desc')

const searchActive = computed(() => listFilter.value.trim() !== '')

function toggleSort(key: Exclude<SortKey, null>) {
  if (sortKey.value === key) {
    sortDir.value = sortDir.value === 'asc' ? 'desc' : 'asc'
  } else {
    sortKey.value = key
    sortDir.value = 'desc'
  }
}

function clearSort() {
  sortKey.value = null
}

function sortMark(key: Exclude<SortKey, null>): string {
  if (sortKey.value !== key) return ''
  return sortDir.value === 'asc' ? ' ▲' : ' ▼'
}

const scoreSortKey = computed((): Exclude<SortKey, null> | null => {
  const id = field.value
  if (id === 'change_pct') return null
  if (id === 'turnover_rate' || id === 'amount' || id === 'volume_ratio') {
    return id
  }
  return null
})

type BoardKey = 'all' | 'main' | 'gem' | 'star' | 'bse'
const boardFilter = ref<BoardKey>('all')
const boardOptions: { key: BoardKey; label: string }[] = [
  { key: 'all', label: '全部' },
  { key: 'main', label: '沪深主板' },
  { key: 'gem', label: '创业板' },
  { key: 'star', label: '科创板' },
  { key: 'bse', label: '北交所' },
]

function boardOf(r: RankRow): BoardKey {
  const vt = (r.vt_symbol || '').toUpperCase()
  const code = vt.split('.')[0] || ''
  if (vt.endsWith('.SSE')) return code.startsWith('68') ? 'star' : 'main'
  if (vt.endsWith('.SZSE')) return code.startsWith('30') ? 'gem' : 'main'
  if (vt.endsWith('.BSE')) return 'bse'
  return 'all'
}

const displayedRanks = computed(() => {
  const q = listFilter.value.trim().toLowerCase()
  let list = props.ranks
  if (boardFilter.value !== 'all') {
    list = list.filter((r) => boardOf(r) === boardFilter.value)
  }
  if (q) {
    list = list.filter((r) => {
      const vt = (r.vt_symbol || '').toLowerCase()
      const name = (r.name || '').toLowerCase()
      return vt.includes(q) || name.includes(q)
    })
  }
  const key = sortKey.value
  if (!key) return list
  const dir = sortDir.value
  return [...list].sort((a, b) => cmpNullable(a[key], b[key], dir))
})

const ROW_H = 33
const OVERSCAN = 12
const VIRTUAL_MIN = 300
const tableWrapEl = ref<HTMLElement | null>(null)
const scrollTop = ref(0)
const viewportH = ref(0)
const rowH = ref(ROW_H)

const useVirtual = computed(
  () => (props.ranks.length > VIRTUAL_MIN && displayedRanks.value.length > VIRTUAL_MIN) || false,
)

const virtualWindow = computed(() => {
  const list = displayedRanks.value
  const total = list.length
  if (total === 0) return { rows: [], padTop: 0, padBottom: 0, offset: 0 }
  const h = rowH.value || ROW_H
  const start = Math.max(0, Math.floor(scrollTop.value / h) - OVERSCAN)
  const end = Math.min(total, Math.ceil((scrollTop.value + viewportH.value) / h) + OVERSCAN)
  return {
    rows: list.slice(start, end),
    padTop: start * h,
    padBottom: Math.max(0, (total - end) * h),
    offset: start,
  }
})

function measureTable() {
  const el = tableWrapEl.value
  if (!el) return
  viewportH.value = el.clientHeight
  const tr = el.querySelector('tbody tr:not(.vpad)')
  if (tr) rowH.value = tr.getBoundingClientRect().height || ROW_H
}

function onTableScroll() {
  scrollTop.value = tableWrapEl.value?.scrollTop || 0
}

watch(displayedRanks, () => {
  scrollTop.value = 0
  void nextTick(() => measureTable())
})

watch(searchActive, (active, prev) => {
  if (active === prev) return
  scrollTop.value = 0
  emit('search-active', active)
})

watch(field, () => {
  const sk = sortKey.value
  if (sk && sk !== 'last_price' && sk !== 'change_pct' && sk !== field.value) {
    sortKey.value = null
  }
})

watch(rankLimit, () => {
  scrollTop.value = 0
})

const condCols = [
  'change_pct',
  'change_amount',
  'turnover_rate',
  'volume_ratio',
  'total_mv',
  'industry',
  'trade_time',
  'amplitude',
] as const

type CondCol = (typeof condCols)[number]

function colHasValue(r: RankRow, key: CondCol): boolean {
  const v = r[key]
  if (typeof v === 'string') return v.trim() !== ''
  return v != null && !Number.isNaN(v) && v !== 0
}

const colVisible = computed(() => {
  const map = {} as Record<CondCol, boolean>
  for (const key of condCols) map[key] = props.ranks.some((r) => colHasValue(r, key))
  return map
})

const emptyColspan = computed(() => 7 + condCols.filter((k) => colVisible.value[k]).length)

function scoreLabel(r: RankRow): string {
  const id = field.value
  if (id === 'change_pct') return formatNum2(r.change_pct)
  if (id === 'turnover_rate') return formatNum2(r.turnover_rate)
  if (id === 'amount') return formatAmountYi(r.amount)
  if (id === 'volume_ratio') return formatNum2(r.volume_ratio)
  return r.score.toFixed(2)
}

function fmtNum(v: number | null | undefined, digits = 2): string {
  if (v == null || Number.isNaN(v)) return '—'
  return v.toFixed(digits)
}

function fmtAmount(v: number | null | undefined): string {
  if (v == null || Number.isNaN(v) || v <= 0) return '—'
  if (v >= 1e8) return (v / 1e8).toFixed(2) + '亿'
  if (v >= 1e4) return (v / 1e4).toFixed(1) + '万'
  return v.toFixed(0)
}

function fmtSigned(v: number | null | undefined): string {
  if (v == null || Number.isNaN(v)) return '—'
  return (v > 0 ? '+' : '') + v.toFixed(2)
}

function fmtMv(v: number | null | undefined): string {
  if (v == null || Number.isNaN(v) || v <= 0) return '—'
  if (v >= 1e8) return (v / 1e8).toFixed(2) + '万亿'
  if (v >= 1e4) return (v / 1e4).toFixed(2) + '亿'
  return v.toFixed(0) + '万'
}

function fmtTime(raw: string | null | undefined): string {
  if (!raw) return '—'
  return raw.slice(0, 5)
}

let resizeObs: ResizeObserver | undefined

onMounted(() => {
  void nextTick(() => measureTable())
  resizeObs = new ResizeObserver(() => measureTable())
  if (tableWrapEl.value) resizeObs.observe(tableWrapEl.value)
})

onUnmounted(() => {
  resizeObs?.disconnect()
})
</script>

<template>
  <div class="toolbar">
    <div class="tabs">
      <button
        v-for="f in fields"
        :key="f.id"
        type="button"
        :class="{ on: field === f.id }"
        @click="field = f.id"
      >
        {{ f.label }}
      </button>
    </div>
    <div class="actions">
      <label class="auto">
        <input v-model="autoRefresh" type="checkbox" />
        {{ refreshLabel }}
      </label>
      <div class="limits">
        <button
          v-for="n in rankLimitChoices"
          :key="n"
          type="button"
          class="chip"
          :class="{ on: searchActive ? n === 0 : rankLimit === n }"
          :disabled="searchActive"
          @click="rankLimit = n"
        >
          {{ rankLimitLabel(n) }}
        </button>
      </div>
      <button class="ghost" type="button" :disabled="loading" @click="emit('refresh')">刷新</button>
      <RouterLink to="/sectors" class="cross-link">板块资金 →</RouterLink>
    </div>
  </div>

  <p v-if="error" class="err">{{ error }}</p>

  <div v-if="ranks.length" class="filter-row">
    <input v-model="listFilter" placeholder="过滤代码/名称" />
    <div class="board-filter">
      <button
        v-for="b in boardOptions"
        :key="b.key"
        type="button"
        class="chip"
        :class="{ on: boardFilter === b.key }"
        @click="boardFilter = b.key"
      >
        {{ b.label }}
      </button>
    </div>
    <span class="muted count-hint"
      >{{ displayedRanks.length }} 只<span v-if="searchActive" class="search-all-tag"
        >全量搜索</span
      ></span
    >
    <button type="button" class="ghost" :class="{ on: !sortKey }" @click="clearSort">默认序</button>
  </div>

  <div class="split">
    <div ref="tableWrapEl" class="table-wrap" @scroll.passive="onTableScroll">
      <p v-if="ranks.length && !displayedRanks.length" class="muted empty-hint">无匹配标的</p>
      <table v-else>
        <thead>
          <tr>
            <th>#</th>
            <th>代码</th>
            <th>名称</th>
            <th class="sortable" @click="toggleSort('last_price')">
              现价{{ sortMark('last_price') }}
            </th>
            <th v-if="colVisible.change_pct" class="sortable" @click="toggleSort('change_pct')">
              涨幅%{{ sortMark('change_pct') }}
            </th>
            <th
              v-if="colVisible.change_amount"
              class="sortable"
              @click="toggleSort('change_amount')"
            >
              涨跌额{{ sortMark('change_amount') }}
            </th>
            <th v-if="scoreSortKey" class="sortable" @click="toggleSort(scoreSortKey)">
              {{ fieldMeta.col }}{{ sortMark(scoreSortKey) }}
            </th>
            <th v-else>{{ fieldMeta.col }}</th>
            <th
              v-if="colVisible.turnover_rate"
              class="sortable"
              @click="toggleSort('turnover_rate')"
            >
              换手%{{ sortMark('turnover_rate') }}
            </th>
            <th
              v-if="colVisible.volume_ratio"
              class="sortable"
              @click="toggleSort('volume_ratio')"
            >
              量比{{ sortMark('volume_ratio') }}
            </th>
            <th v-if="colVisible.total_mv" class="sortable" @click="toggleSort('total_mv')">
              总市值{{ sortMark('total_mv') }}
            </th>
            <th v-if="colVisible.industry">行业</th>
            <th v-if="colVisible.trade_time">时间</th>
            <th v-if="colVisible.amplitude" class="sortable" @click="toggleSort('amplitude')">
              振幅%{{ sortMark('amplitude') }}
            </th>
            <th class="sortable" @click="toggleSort('amount')">成交额{{ sortMark('amount') }}</th>
            <th class="ops">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="useVirtual && virtualWindow.padTop" class="vpad">
            <td :colspan="emptyColspan" :style="{ height: virtualWindow.padTop + 'px' }"></td>
          </tr>
          <template
            v-for="(r, j) in useVirtual ? virtualWindow.rows : displayedRanks"
            :key="r.tf_symbol"
          >
            <tr>
              <td>
                <span
                  class="rank-badge"
                  :class="'rank-' + ((useVirtual ? virtualWindow.offset + j : j) + 1)"
                  >{{ (useVirtual ? virtualWindow.offset + j : j) + 1 }}</span
                >
              </td>
              <td class="mono">{{ r.vt_symbol }}</td>
              <td>{{ r.name || '—' }}</td>
              <td>{{ formatPrice(r.last_price) }}</td>
              <td
                v-if="colVisible.change_pct"
                :class="{ up: (r.change_pct || 0) > 0, down: (r.change_pct || 0) < 0 }"
              >
                {{ formatNum2(r.change_pct) }}
              </td>
              <td
                v-if="colVisible.change_amount"
                :class="{ up: (r.change_amount || 0) > 0, down: (r.change_amount || 0) < 0 }"
              >
                {{ fmtSigned(r.change_amount) }}
              </td>
              <td>{{ scoreLabel(r) }}</td>
              <td v-if="colVisible.turnover_rate">
                {{ formatNum2(r.turnover_rate) }}
              </td>
              <td v-if="colVisible.volume_ratio">
                {{ formatNum2(r.volume_ratio) }}
              </td>
              <td v-if="colVisible.total_mv" class="mono muted">{{ fmtMv(r.total_mv) }}</td>
              <td v-if="colVisible.industry">{{ r.industry || '—' }}</td>
              <td v-if="colVisible.trade_time" class="mono muted">
                {{ fmtTime(r.trade_time) }}
              </td>
              <td v-if="colVisible.amplitude">{{ fmtNum(r.amplitude, 2) }}</td>
              <td>{{ fmtAmount(r.amount) }}</td>
              <td class="ops">
                <div class="row-ops">
                  <button type="button" class="icon-btn" title="K线" @click="emit('chart', r.vt_symbol)">
                    <svg
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      stroke-width="1.6"
                      stroke-linecap="round"
                      stroke-linejoin="round"
                    >
                      <path
                        d="M5 4v2.5M5 17.5V20M5 6.5a1.5 1.5 0 011.5-1.5h0A1.5 1.5 0 018 6.5v11a1.5 1.5 0 01-1.5 1.5h0A1.5 1.5 0 015 17.5v-11z"
                      />
                      <path
                        d="M12 2v4M12 18v4M12 6a1.5 1.5 0 011.5-1.5h0A1.5 1.5 0 0115 6v12a1.5 1.5 0 01-1.5 1.5h0A1.5 1.5 0 0112 18V6z"
                      />
                      <path
                        d="M19 6v3M19 17v4M19 9a1.5 1.5 0 011.5-1.5h0a1.5 1.5 0 011.5 1.5v8a1.5 1.5 0 01-1.5 1.5h0a1.5 1.5 0 01-1.5-1.5V9z"
                      />
                    </svg>
                  </button>
                  <button
                    type="button"
                    class="icon-btn"
                    :class="{ on: watchSet.has(r.vt_symbol) }"
                    :title="watchSet.has(r.vt_symbol) ? '在自选，点击移除' : '加自选'"
                    @click="emit('toggle-watch', r)"
                  >
                    <svg
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      stroke-width="1.6"
                      stroke-linecap="round"
                      stroke-linejoin="round"
                    >
                      <path
                        d="M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.69h4.915c.969 0 1.371 1.24.588 1.81l-3.976 2.888a1 1 0 00-.363 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.976-2.888a1 1 0 00-1.176 0l-3.976 2.888c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 00-.363-1.118l-3.976-2.888c-.784-.57-.38-1.81.588-1.81h4.914a1 1 0 00.951-.69l1.519-4.674z"
                      />
                    </svg>
                  </button>
                  <button type="button" class="icon-btn" title="基本面" @click="emit('fund', r.vt_symbol)">
                    <svg
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      stroke-width="1.6"
                      stroke-linecap="round"
                      stroke-linejoin="round"
                    >
                      <path d="M3 3h18v18H3V3zM7 7h10M7 11h10M7 15h6" />
                    </svg>
                  </button>
                  <button
                    type="button"
                    class="icon-btn"
                    title="分析"
                    @click.stop="emit('analyze', r.vt_symbol, r.name)"
                  >
                    <svg
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      stroke-width="1.6"
                      stroke-linecap="round"
                      stroke-linejoin="round"
                    >
                      <path
                        d="M8.25 21v-4.875c0-.621.504-1.125 1.125-1.125h5.25c.621 0 1.125.504 1.125 1.125V21m0 0h4.5M3.75 21h4.5M3.75 21V9m0 0l-1.5 3M3.75 9l9-6 9 6m-13.5 0v6h4.5v-6"
                      />
                    </svg>
                  </button>
                </div>
              </td>
            </tr>
          </template>
          <tr v-if="useVirtual && virtualWindow.padBottom" class="vpad">
            <td :colspan="emptyColspan" :style="{ height: virtualWindow.padBottom + 'px' }"></td>
          </tr>
          <tr v-if="!ranks.length">
            <td :colspan="emptyColspan" class="empty">
              暂无排行（需 Redis 行情快照）
              <RouterLink to="/ops" class="draft-link">去 Ops</RouterLink>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<style scoped>
.draft-link {
  color: var(--brand);
  margin-left: 4px;
}
.cross-link {
  color: var(--brand);
  text-decoration: none;
  font-size: 0.85rem;
  white-space: nowrap;
}
.cross-link:hover {
  text-decoration: underline;
}
.toolbar {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
  flex-wrap: wrap;
}
.tabs,
.actions {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  align-items: center;
}
.tabs button {
  background: var(--surface);
  border: 1px solid var(--line);
  color: var(--ink-muted);
  border-radius: 0.5rem;
  padding: 7px 12px;
  font-size: 0.8125rem;
  transition:
    background 0.15s ease,
    color 0.15s ease,
    border-color 0.15s ease;
}
.tabs button:hover {
  color: var(--ink);
  border-color: var(--brand-soft);
}
.tabs button.on {
  background: var(--brand-light);
  color: var(--brand);
  border-color: var(--brand-soft);
  font-weight: 500;
}
.auto {
  display: flex;
  gap: 6px;
  align-items: center;
  color: var(--muted);
  font-size: 0.8rem;
}
.ghost {
  border-radius: 0.5rem;
  padding: 6px 10px;
  border: 1px solid var(--border);
  cursor: pointer;
  background: transparent;
  color: var(--text);
}
.ghost.on {
  border-color: var(--brand, #333);
  color: var(--text);
  font-weight: 500;
}
.filter-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}
.board-filter {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
}
.count-hint {
  font-size: 0.8rem;
  font-variant-numeric: tabular-nums;
}
.search-all-tag {
  margin-left: 6px;
  font-size: 0.72rem;
  color: var(--brand);
  background: var(--brand-light);
  border: 1px solid var(--brand-soft);
  border-radius: 999px;
  padding: 1px 8px;
  font-variant-numeric: normal;
}
.filter-row input {
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: 0.5rem;
  color: var(--text);
  padding: 6px 10px;
  min-width: 160px;
}
.empty-hint {
  margin: 0;
  padding: 12px;
}
.err {
  margin: 0;
  color: var(--danger);
  font-size: 0.85rem;
}
.muted {
  color: var(--muted);
}
.split {
  display: grid;
  gap: 12px;
  min-height: 420px;
}
.table-wrap {
  border: 1px solid var(--line);
  border-radius: 0.75rem;
  background: var(--surface);
  box-shadow: var(--shadow-card);
  overflow: auto;
  max-height: 70vh;
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
.chip:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}
.chip.on {
  background: var(--brand-light);
  color: var(--brand);
  border-color: var(--brand-soft);
  font-weight: 500;
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
.icon-btn.on {
  color: var(--brand);
  border-color: var(--brand-soft);
  background: var(--brand-light);
}
.row-ops {
  display: flex;
  gap: 4px;
}
th.ops,
td.ops {
  text-align: right;
}
th.sortable {
  cursor: pointer;
  user-select: none;
}
th.sortable:hover {
  color: var(--text);
}
.rank-badge {
  display: inline-grid;
  place-items: center;
  min-width: 24px;
  height: 20px;
  border-radius: 999px;
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--ink-muted);
  background: var(--surface-muted);
  font-variant-numeric: tabular-nums;
}
.rank-badge.rank-1 {
  background: #fde8d7;
  color: #b45309;
}
.rank-badge.rank-2 {
  background: #eef0f3;
  color: #52525b;
}
.rank-badge.rank-3 {
  background: #fbe3dc;
  color: #9a5b3f;
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
</style>

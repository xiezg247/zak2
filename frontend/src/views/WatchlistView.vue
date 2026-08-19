<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import AppShell from '../components/AppShell.vue'
import CandleChart from '../components/CandleChart.vue'
import StockAnalysisModal from '../components/StockAnalysisModal.vue'
import { confirmDialog, promptDialog } from '../lib/dialog'
import {
  watchlistApi,
  type Bar,
  type Fundamentals,
  type GroupMembersBatchResult,
  type WatchlistGroup,
  type WatchlistItem,
} from '../api/watchlist'
import { POLL_FAST_MS, POLL_SLOW_MS, useQuoteNotify } from '../composables/useQuoteNotify'
import { useStockAnalysis } from '../composables/useStockAnalysis'

const analysis = useStockAnalysis()

const route = useRoute()
const items = ref<WatchlistItem[]>([])
const groups = ref<WatchlistGroup[]>([])
const groupId = ref<string>('')
const addSymbol = ref('')
const newGroup = ref('')
const error = ref('')
const loading = ref(false)
const autoRefresh = ref(true)
const selected = ref<WatchlistItem | null>(null)
const bars = ref<Bar[]>([])
const barsError = ref('')
const barsLoading = ref(false)
const barInterval = ref<'d' | '1m'>('d')
const barLimitDaily = ref(90)
const barLimit1m = ref(480)

const barLimit = computed({
  get: () => (barInterval.value === '1m' ? barLimit1m.value : barLimitDaily.value),
  set: (n: number) => {
    if (barInterval.value === '1m') barLimit1m.value = n
    else barLimitDaily.value = n
  },
})

const barLimitChoices = computed(() =>
  barInterval.value === '1m' ? [240, 480, 1200] : [60, 90, 120],
)
const fundOpen = ref(true)
const fundLoading = ref(false)
const fundError = ref('')
const fund = ref<Fundamentals | null>(null)
const lastRefresh = ref('')
let timer: number | undefined

const { connected } = useQuoteNotify({
  onQuotesUpdated: () => {
    if (!autoRefresh.value || document.hidden) return
    void refresh(true)
  },
})

function restartPoll() {
  if (timer) window.clearInterval(timer)
  const ms = connected.value ? POLL_SLOW_MS : POLL_FAST_MS
  timer = window.setInterval(tick, ms)
}

watch(connected, () => restartPoll())

const subtitle = computed(() => {
  const n = items.value.length
  const sel = selected.value?.vt_symbol
  const ts = lastRefresh.value ? ` · ${lastRefresh.value}` : ''
  return sel ? `${n} 只 · ${sel}${ts}` : `${n} 只自选${ts}`
})

type SortKey = 'last_price' | 'change_pct' | 'turnover_rate' | 'volume_ratio' | 'amount' | null

const listFilter = ref('')
const sortKey = ref<SortKey>(null)
const sortDir = ref<'asc' | 'desc'>('desc')
const checked = ref<Set<string>>(new Set())
const batchTargetGroupId = ref('')
const batchMsg = ref('')

const COL_PREFS_KEY = 'zak2:watchlist:list_columns'

type OptionalCol = 'industry' | 'turnover_rate' | 'volume_ratio' | 'amount'

const DEFAULT_COL_VISIBLE: Record<OptionalCol, boolean> = {
  industry: true,
  turnover_rate: true,
  volume_ratio: true,
  amount: true,
}

const columnsOpen = ref(false)
const colVisible = ref<Record<OptionalCol, boolean>>({ ...DEFAULT_COL_VISIBLE })

function loadColPrefs() {
  try {
    const raw = localStorage.getItem(COL_PREFS_KEY)
    if (!raw) return
    const parsed = JSON.parse(raw) as Partial<Record<OptionalCol, unknown>>
    const next = { ...DEFAULT_COL_VISIBLE }
    for (const k of Object.keys(DEFAULT_COL_VISIBLE) as OptionalCol[]) {
      if (typeof parsed[k] === 'boolean') next[k] = parsed[k] as boolean
    }
    colVisible.value = next
  } catch {
    colVisible.value = { ...DEFAULT_COL_VISIBLE }
  }
}

function saveColPrefs() {
  localStorage.setItem(COL_PREFS_KEY, JSON.stringify(colVisible.value))
}

function setColVisible(key: OptionalCol, on: boolean) {
  colVisible.value = { ...colVisible.value, [key]: on }
  if (!on && sortKey.value === key) clearSort()
  saveColPrefs()
}

const optionalColLabels: { key: OptionalCol; label: string }[] = [
  { key: 'industry', label: '行业' },
  { key: 'turnover_rate', label: '换手%' },
  { key: 'volume_ratio', label: '量比' },
  { key: 'amount', label: '成交额' },
]

const tableColspan = computed(() => {
  let n = 6
  for (const k of Object.keys(DEFAULT_COL_VISIBLE) as OptionalCol[]) {
    if (colVisible.value[k]) n += 1
  }
  return n
})

const groupIndex = computed(() => {
  if (!groupId.value) return -1
  return groups.value.findIndex((g) => g.id === groupId.value)
})

const otherGroups = computed(() => groups.value.filter((g) => g.id !== groupId.value))

const hasChecked = computed(() => checked.value.size > 0)

const allDisplayedChecked = computed(() => {
  const rows = displayedItems.value
  if (!rows.length) return false
  return rows.every((r) => checked.value.has(r.vt_symbol))
})

function formatAmountYi(v: number | null | undefined): string {
  if (v == null || Number.isNaN(v)) return '—'
  return `${(v / 1e8).toFixed(2)}亿`
}

function formatNum2(v: number | null | undefined): string {
  if (v == null || Number.isNaN(v)) return '—'
  return v.toFixed(2)
}

function cmpNullable(
  a: number | null | undefined,
  b: number | null | undefined,
  dir: 'asc' | 'desc',
): number {
  const aMissing = a == null || Number.isNaN(a)
  const bMissing = b == null || Number.isNaN(b)
  if (aMissing && bMissing) return 0
  if (aMissing) return 1 // 垫底
  if (bMissing) return -1
  const d = (a as number) - (b as number)
  return dir === 'asc' ? d : -d
}

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

const displayedItems = computed(() => {
  const q = listFilter.value.trim().toLowerCase()
  let rows = items.value
  if (q) {
    rows = rows.filter((it) => {
      const vt = (it.vt_symbol || '').toLowerCase()
      const name = (it.name || '').toLowerCase()
      return vt.includes(q) || name.includes(q)
    })
  }
  const key = sortKey.value
  if (!key) return rows
  const dir = sortDir.value
  return [...rows].sort((a, b) => cmpNullable(a[key], b[key], dir))
})

function sortMark(key: Exclude<SortKey, null>): string {
  if (sortKey.value !== key) return ''
  return sortDir.value === 'asc' ? ' ▲' : ' ▼'
}

async function refresh(quiet = false) {
  if (!quiet) loading.value = true
  error.value = ''
  try {
    const [list, gs] = await Promise.all([
      watchlistApi.list(groupId.value || undefined),
      watchlistApi.groups(),
    ])
    items.value = list
    groups.value = gs
    lastRefresh.value = new Date().toLocaleTimeString()
    if (selected.value) {
      const still = list.find((i) => i.vt_symbol === selected.value?.vt_symbol)
      selected.value = still || list[0] || null
    } else if (list.length) {
      selected.value = list[0]
    }
  } catch (e) {
    error.value = e instanceof Error ? e.message : '加载失败'
  } finally {
    loading.value = false
  }
}

async function loadBars() {
  barsError.value = ''
  bars.value = []
  if (!selected.value) {
    barsLoading.value = false
    return
  }
  barsLoading.value = true
  try {
    const resp = await watchlistApi.bars(
      selected.value.vt_symbol,
      barInterval.value,
      barLimit.value,
    )
    bars.value = resp.bars
  } catch (e) {
    barsError.value = e instanceof Error ? e.message : '无 K 线'
  } finally {
    barsLoading.value = false
  }
}

function formatYmd(raw: string | null | undefined): string {
  const s = (raw || '').trim()
  if (!s) return '—'
  if (/^\d{8}$/.test(s)) return `${s.slice(0, 4)}-${s.slice(4, 6)}-${s.slice(6, 8)}`
  return s
}

function formatMoney(n: number | null | undefined): string {
  if (n == null || Number.isNaN(n)) return '—'
  if (Math.abs(n) >= 1e8) return `${(n / 1e8).toFixed(2)} 亿`
  if (Math.abs(n) >= 1e4) return `${(n / 1e4).toFixed(2)} 万`
  return n.toFixed(2)
}

function formatRatioPct(n: number | null | undefined): string {
  if (n == null || Number.isNaN(n)) return '—'
  return `${(n * 100).toFixed(1)}%`
}

async function loadFundamentals() {
  fundError.value = ''
  fund.value = null
  if (!selected.value) {
    fundLoading.value = false
    return
  }
  fundLoading.value = true
  try {
    fund.value = await watchlistApi.fundamentals(selected.value.vt_symbol)
  } catch (e) {
    fundError.value = e instanceof Error ? e.message : '基本面加载失败'
  } finally {
    fundLoading.value = false
  }
}

async function onAdd() {
  error.value = ''
  try {
    await watchlistApi.add(addSymbol.value.trim())
    addSymbol.value = ''
    await refresh()
  } catch (e) {
    error.value = e instanceof Error ? e.message : '添加失败'
  }
}

async function onRemove(item: WatchlistItem) {
  error.value = ''
  try {
    await watchlistApi.remove(item.vt_symbol)
    if (selected.value?.vt_symbol === item.vt_symbol) selected.value = null
    await refresh()
  } catch (e) {
    error.value = e instanceof Error ? e.message : '删除失败'
  }
}

async function onCreateGroup() {
  const name = newGroup.value.trim()
  if (!name) return
  try {
    await watchlistApi.createGroup(name)
    newGroup.value = ''
    await refresh()
  } catch (e) {
    error.value = e instanceof Error ? e.message : '创建分组失败'
  }
}

async function onRenameGroup() {
  if (!groupId.value) return
  const cur = groups.value.find((g) => g.id === groupId.value)
  const next = await promptDialog({
    title: '重命名分组',
    initialValue: cur?.name || '',
    placeholder: '新分组名',
  })
  if (next == null) return
  const name = next.trim()
  if (!name) {
    error.value = '分组名不能为空'
    return
  }
  try {
    error.value = ''
    await watchlistApi.renameGroup(groupId.value, name)
    await refresh()
  } catch (e) {
    error.value = e instanceof Error ? e.message : '改名失败'
  }
}

async function onDeleteGroup() {
  if (!groupId.value) return
  const ok = await confirmDialog({
    title: '删除分组',
    message: '确定删除该分组？自选标的不会被删除',
    danger: true,
  })
  if (!ok) return
  try {
    error.value = ''
    await watchlistApi.deleteGroup(groupId.value)
    groupId.value = ''
    checked.value = new Set()
    await refresh()
  } catch (e) {
    error.value = e instanceof Error ? e.message : '删组失败'
  }
}

async function onMoveGroup(delta: -1 | 1) {
  const idx = groupIndex.value
  if (idx < 0) return
  const next = idx + delta
  if (next < 0 || next >= groups.value.length) return
  const reordered = [...groups.value]
  const tmp = reordered[idx]
  reordered[idx] = reordered[next]
  reordered[next] = tmp
  try {
    error.value = ''
    const gs = await watchlistApi.reorderGroups(reordered.map((g) => g.id))
    groups.value = gs
  } catch (e) {
    error.value = e instanceof Error ? e.message : '排序失败'
  }
}

function toggleChecked(vt: string) {
  const next = new Set(checked.value)
  if (next.has(vt)) next.delete(vt)
  else next.add(vt)
  checked.value = next
}

function toggleAllDisplayed() {
  const rows = displayedItems.value
  if (allDisplayedChecked.value) {
    checked.value = new Set()
  } else {
    checked.value = new Set(rows.map((r) => r.vt_symbol))
  }
}

function formatBatchResult(result: GroupMembersBatchResult): string {
  const parts: string[] = []
  const n = result.action === 'add' ? result.added : result.removed
  if (n > 0) parts.push(`${result.action === 'add' ? '加入' : '移出'} ${n} 只`)
  if (result.skipped > 0) parts.push(`跳过 ${result.skipped}`)
  if (result.errors.length > 0) parts.push(`${result.errors.length} 条失败`)
  return parts.join('，') || '已完成'
}

async function onBatchAddToGroup() {
  if (!batchTargetGroupId.value || checked.value.size === 0) return
  try {
    error.value = ''
    batchMsg.value = ''
    const symbols = [...checked.value]
    const result = await watchlistApi.batchGroupMembers(batchTargetGroupId.value, symbols, 'add')
    checked.value = new Set()
    batchMsg.value = formatBatchResult(result)
    if (result.skipped > 0 || result.errors.length > 0) {
      error.value = batchMsg.value
    }
    await refresh()
  } catch (e) {
    error.value = e instanceof Error ? e.message : '批量加入失败'
  }
}

async function onBatchRemoveFromGroup() {
  if (!groupId.value || checked.value.size === 0) return
  try {
    error.value = ''
    batchMsg.value = ''
    const symbols = [...checked.value]
    const result = await watchlistApi.batchGroupMembers(groupId.value, symbols, 'remove')
    checked.value = new Set()
    batchMsg.value = formatBatchResult(result)
    if (result.skipped > 0 || result.errors.length > 0) {
      error.value = batchMsg.value
    }
    await refresh()
  } catch (e) {
    error.value = e instanceof Error ? e.message : '批量移出失败'
  }
}

async function onAddToGroup() {
  if (!groupId.value || !selected.value) return
  try {
    error.value = ''
    await watchlistApi.addToGroup(groupId.value, selected.value.vt_symbol)
    await refresh()
  } catch (e) {
    error.value = e instanceof Error ? e.message : '加入分组失败'
  }
}

async function onRemoveFromGroup() {
  if (!groupId.value || !selected.value) return
  try {
    error.value = ''
    await watchlistApi.removeFromGroup(groupId.value, selected.value.vt_symbol)
    await refresh()
  } catch (e) {
    error.value = e instanceof Error ? e.message : '移出分组失败'
  }
}

function selectRow(item: WatchlistItem) {
  selected.value = item
}

function tick() {
  if (!autoRefresh.value) return
  if (document.hidden) return
  void refresh(true)
}

watch(selected, () => {
  void loadBars()
  void loadFundamentals()
})

watch(groupId, () => {
  checked.value = new Set()
  batchTargetGroupId.value = ''
  batchMsg.value = ''
})

watch([barLimit, barInterval], () => {
  void loadBars()
})

onMounted(async () => {
  loadColPrefs()
  await refresh(false)
  const q = String(route.query.symbol || '').trim()
  if (q) {
    const hit = items.value.find((i) => i.vt_symbol === q || i.tf_symbol === q)
    if (hit) selected.value = hit
    else {
      try {
        await watchlistApi.add(q)
        await refresh(true)
        selected.value =
          items.value.find((i) => i.vt_symbol.includes(q.split('.')[0])) || selected.value
      } catch {
        /* ignore */
      }
    }
  }
  timer = window.setInterval(tick, connected.value ? POLL_SLOW_MS : POLL_FAST_MS)
})

onUnmounted(() => {
  if (timer) window.clearInterval(timer)
})
</script>

<template>
  <AppShell title="自选" :subtitle="subtitle" active="watchlist">
    <div class="page">
      <div class="workspace">
        <section class="left">
          <div class="block">
            <div class="block-head">
              <span class="block-title">分组</span>
              <div class="block-head-actions">
                <button
                  type="button"
                  class="ghost sm"
                  :disabled="groupIndex <= 0"
                  @click="onMoveGroup(-1)"
                >
                  上移
                </button>
                <button
                  type="button"
                  class="ghost sm"
                  :disabled="groupIndex < 0 || groupIndex >= groups.length - 1"
                  @click="onMoveGroup(1)"
                >
                  下移
                </button>
              </div>
            </div>
            <div class="row group-row">
              <select v-model="groupId" @change="refresh()">
                <option value="">全部自选</option>
                <option v-for="g in groups" :key="g.id" :value="g.id">{{ g.name }}</option>
              </select>
              <input v-model="newGroup" placeholder="新分组名" @keyup.enter="onCreateGroup" />
              <button type="button" class="ghost" @click="onCreateGroup">建组</button>
              <button v-if="groupId" type="button" class="ghost" @click="onRenameGroup">
                改名
              </button>
              <button v-if="groupId" type="button" class="ghost" @click="onDeleteGroup">
                删组
              </button>
            </div>
            <div v-if="groupId && selected" class="row">
              <button type="button" class="ghost" @click="onAddToGroup">加入此组</button>
              <button type="button" class="ghost" @click="onRemoveFromGroup">移出此组</button>
            </div>
          </div>

          <div class="block">
            <div class="block-head">
              <span class="block-title">自选</span>
              <div class="block-head-actions">
                <RouterLink class="ghost sm" to="/board">看板</RouterLink>
                <label class="auto">
                  <input v-model="autoRefresh" type="checkbox" />
                  {{ connected ? 'WS 推送 + 慢轮询' : '每 15s 刷新行情' }}
                </label>
                <button type="button" class="ghost sm" :disabled="loading" @click="refresh()">
                  刷新
                </button>
              </div>
            </div>
            <div class="row add-row">
              <input v-model="addSymbol" placeholder="添加代码 600519.SSE" @keyup.enter="onAdd" />
              <button type="button" class="primary" @click="onAdd">添加</button>
              <input v-model="listFilter" placeholder="过滤代码/名称" />
              <button v-if="sortKey" type="button" class="ghost" @click="clearSort">默认序</button>
              <button
                type="button"
                class="ghost"
                :class="{ on: columnsOpen }"
                @click="columnsOpen = !columnsOpen"
              >
                列
              </button>
            </div>
            <div v-if="columnsOpen" class="col-prefs-panel">
              <label v-for="c in optionalColLabels" :key="c.key" class="col-pref-item">
                <input
                  type="checkbox"
                  :checked="colVisible[c.key]"
                  @change="setColVisible(c.key, ($event.target as HTMLInputElement).checked)"
                />
                {{ c.label }}
              </label>
            </div>
          </div>

          <p v-if="error" class="err">{{ error }}</p>
          <p v-else-if="batchMsg" class="muted">{{ batchMsg }}</p>
          <p v-if="loading" class="muted">刷新中…</p>

          <div v-if="hasChecked" class="row batch-bar">
            <span class="muted batch-count">已选 {{ checked.size }} 只</span>
            <label>
              目标组
              <select v-model="batchTargetGroupId">
                <option value="">选择分组</option>
                <option v-for="g in otherGroups" :key="g.id" :value="g.id">{{ g.name }}</option>
              </select>
            </label>
            <button
              type="button"
              class="ghost"
              :disabled="!batchTargetGroupId"
              @click="onBatchAddToGroup"
            >
              批量加入
            </button>
            <button v-if="groupId" type="button" class="ghost" @click="onBatchRemoveFromGroup">
              批量移出此组
            </button>
          </div>

          <div class="table-wrap">
            <table>
              <thead>
                <tr>
                  <th class="check-col">
                    <input
                      type="checkbox"
                      :checked="allDisplayedChecked"
                      :disabled="!displayedItems.length"
                      @change="toggleAllDisplayed"
                    />
                  </th>
                  <th>代码</th>
                  <th>名称</th>
                  <th v-if="colVisible.industry">行业</th>
                  <th class="sortable" @click="toggleSort('last_price')">
                    现价{{ sortMark('last_price') }}
                  </th>
                  <th class="sortable" @click="toggleSort('change_pct')">
                    涨幅%{{ sortMark('change_pct') }}
                  </th>
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
                  <th v-if="colVisible.amount" class="sortable" @click="toggleSort('amount')">
                    成交额{{ sortMark('amount') }}
                  </th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="item in displayedItems"
                  :key="item.vt_symbol"
                  :class="{ on: selected?.vt_symbol === item.vt_symbol }"
                  @click="selectRow(item)"
                >
                  <td class="check-col" @click.stop>
                    <input
                      type="checkbox"
                      :checked="checked.has(item.vt_symbol)"
                      @change="toggleChecked(item.vt_symbol)"
                    />
                  </td>
                  <td class="mono">{{ item.vt_symbol }}</td>
                  <td>
                    {{ item.name || '—' }}
                    <span v-if="item.suspended" class="suspend-tag" title="停牌">停</span>
                  </td>
                  <td v-if="colVisible.industry">
                    {{ item.industry?.trim() ? item.industry : '—' }}
                  </td>
                  <td>{{ formatNum2(item.last_price) }}</td>
                  <td
                    :class="{
                      up: (item.change_pct || 0) > 0,
                      down: (item.change_pct || 0) < 0,
                    }"
                  >
                    {{ formatNum2(item.change_pct) }}
                  </td>
                  <td v-if="colVisible.turnover_rate">{{ formatNum2(item.turnover_rate) }}</td>
                  <td v-if="colVisible.volume_ratio">{{ formatNum2(item.volume_ratio) }}</td>
                  <td v-if="colVisible.amount">{{ formatAmountYi(item.amount) }}</td>
                  <td>
                    <button
                      type="button"
                      class="link"
                      @click.stop="analysis.open(item.vt_symbol, item.name)"
                    >
                      析
                    </button>
                    <button type="button" class="link" @click.stop="onRemove(item)">删</button>
                  </td>
                </tr>
                <tr v-if="!displayedItems.length">
                  <td :colspan="tableColspan" class="empty">
                    {{ items.length === 0 ? '暂无自选标的，上方输入代码添加' : '无匹配标的' }}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>

        <section class="right">
          <div v-if="selected" class="chart-head">
            <div class="quote-id">
              <div class="quote-name">
                <strong>{{ selected.name || selected.vt_symbol }}</strong>
                <span v-if="selected.suspended" class="suspend-tag" title="停牌">停</span>
              </div>
              <div class="quote-meta">
                <span class="mono muted">{{ selected.vt_symbol }}</span>
                <span v-if="selected.industry?.trim()" class="muted"
                  >· {{ selected.industry }}</span
                >
              </div>
            </div>
            <div
              class="quote-price"
              :class="{
                up: (selected.change_pct || 0) > 0,
                down: (selected.change_pct || 0) < 0,
              }"
            >
              <span class="price mono">{{
                selected.last_price != null ? selected.last_price.toFixed(2) : '—'
              }}</span>
              <span class="change mono">
                {{
                  selected.change_pct != null
                    ? (selected.change_pct > 0 ? '+' : '') + selected.change_pct.toFixed(2) + '%'
                    : '—'
                }}
              </span>
            </div>
            <div class="limits">
              <button
                type="button"
                class="chip"
                :class="{ on: barInterval === 'd' }"
                @click="barInterval = 'd'"
              >
                日K
              </button>
              <button
                type="button"
                class="chip"
                :class="{ on: barInterval === '1m' }"
                @click="barInterval = '1m'"
              >
                1分
              </button>
            </div>
            <div class="limits">
              <button
                v-for="n in barLimitChoices"
                :key="n"
                type="button"
                class="chip"
                :class="{ on: barLimit === n }"
                @click="barLimit = n"
              >
                {{ barInterval === '1m' ? `${n}根` : `${n}日` }}
              </button>
            </div>
          </div>
          <p v-else class="muted">选择左侧标的查看 K 线</p>
          <template v-if="selected">
            <p v-if="barsLoading" class="muted">
              {{ barInterval === '1m' ? '加载 1 分 K…' : '加载日 K…' }}
            </p>
            <template v-else-if="barsError">
              <p class="err">
                {{ barsError }}
                <RouterLink to="/ops" class="draft-link">{{
                  barInterval === '1m' ? '去 Ops 补全 1 分 K' : '去 Ops 补全日 K'
                }}</RouterLink>
              </p>
            </template>
            <template v-else-if="!bars.length">
              <p class="muted">
                {{ barInterval === '1m' ? '暂无 1 分 K' : '暂无日 K' }}
                <RouterLink to="/ops" class="draft-link">{{
                  barInterval === '1m' ? '去 Ops 补全 1 分 K' : '去 Ops 补全日 K'
                }}</RouterLink>
              </p>
            </template>
            <template v-else>
              <div class="chart">
                <CandleChart :bars="bars" :interval="barInterval" />
                <div class="bar-meta muted">
                  {{ bars[0].datetime.slice(0, barInterval === '1m' ? 16 : 10) }} →
                  {{ bars[bars.length - 1].datetime.slice(0, barInterval === '1m' ? 16 : 10) }}
                  · {{ bars.length }} {{ barInterval === '1m' ? '根 1 分 K' : '根日 K' }}
                </div>
              </div>

              <div class="table-wrap mini">
                <table>
                  <thead>
                    <tr>
                      <th>日期</th>
                      <th>开</th>
                      <th>高</th>
                      <th>低</th>
                      <th>收</th>
                      <th>量</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="b in bars.slice().reverse().slice(0, 20)" :key="b.datetime">
                      <td class="mono">{{ b.datetime.slice(0, 16) }}</td>
                      <td>{{ b.open.toFixed(2) }}</td>
                      <td>{{ b.high.toFixed(2) }}</td>
                      <td>{{ b.low.toFixed(2) }}</td>
                      <td>{{ b.close.toFixed(2) }}</td>
                      <td>{{ Math.round(b.volume).toLocaleString() }}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </template>
          </template>

          <div v-if="selected" class="fund-card">
            <div class="fund-head">
              <h3>基本面</h3>
              <button type="button" class="ghost" @click="fundOpen = !fundOpen">
                {{ fundOpen ? '收起' : '展开' }}
              </button>
            </div>
            <template v-if="fundOpen">
              <p v-if="fundLoading" class="muted">加载基本面…</p>
              <p v-else-if="fundError" class="err">{{ fundError }}</p>
              <template v-else-if="fund">
                <div class="fund-block">
                  <h4>财报</h4>
                  <template v-if="fund.snapshot">
                    <p class="muted">
                      期末 {{ formatYmd(fund.snapshot.end_date) }}
                      <span v-if="fund.sync?.last_sync_at">
                        · 同步 {{ fund.sync.last_sync_at }}</span
                      >
                    </p>
                    <dl class="fund-grid">
                      <div>
                        <dt>营收</dt>
                        <dd class="mono">{{ formatMoney(fund.snapshot.revenue) }}</dd>
                      </div>
                      <div>
                        <dt>净利</dt>
                        <dd class="mono">{{ formatMoney(fund.snapshot.net_income) }}</dd>
                      </div>
                      <div>
                        <dt>营收同比</dt>
                        <dd>{{ formatRatioPct(fund.snapshot.revenue_yoy) }}</dd>
                      </div>
                      <div>
                        <dt>净利同比</dt>
                        <dd>{{ formatRatioPct(fund.snapshot.net_income_yoy) }}</dd>
                      </div>
                      <div>
                        <dt>ROE</dt>
                        <dd>{{ formatRatioPct(fund.snapshot.roe) }}</dd>
                      </div>
                      <div>
                        <dt>资产负债率</dt>
                        <dd>{{ formatRatioPct(fund.snapshot.debt_ratio) }}</dd>
                      </div>
                    </dl>
                  </template>
                  <p v-else class="muted">
                    暂无财报
                    <RouterLink to="/ops" class="draft-link">去 Ops 同步自选财报</RouterLink>
                  </p>
                </div>
                <div class="fund-block">
                  <h4>披露</h4>
                  <template v-if="fund.disclosures.length">
                    <table class="fund-disc">
                      <thead>
                        <tr>
                          <th>报告期</th>
                          <th>预告</th>
                          <th>公告</th>
                          <th>实际</th>
                        </tr>
                      </thead>
                      <tbody>
                        <tr v-for="d in fund.disclosures" :key="d.end_date">
                          <td class="mono">{{ formatYmd(d.end_date) }}</td>
                          <td class="mono">{{ formatYmd(d.pre_date) }}</td>
                          <td class="mono">{{ formatYmd(d.ann_date) }}</td>
                          <td class="mono">{{ formatYmd(d.actual_date) }}</td>
                        </tr>
                      </tbody>
                    </table>
                  </template>
                  <p v-else class="muted">
                    暂无披露日历
                    <RouterLink to="/ops" class="draft-link">去 Ops 同步披露计划</RouterLink>
                  </p>
                </div>
              </template>
            </template>
          </div>
        </section>
      </div>
    </div>
  </AppShell>
  <StockAnalysisModal />
</template>

<style scoped>
.page {
  display: grid;
  grid-template-rows: 1fr;
  height: 100%;
  min-height: 0;
  padding: 0;
}
.workspace {
  display: grid;
  grid-template-columns: 1.1fr 1fr;
  min-height: 0;
  overflow: hidden;
}
.left,
.right {
  padding: 20px 24px;
  overflow: auto;
  display: grid;
  gap: 14px;
  align-content: start;
}
.left {
  border-right: 1px solid var(--line);
  background: var(--surface);
  display: flex;
  flex-direction: column;
}
.right {
  background: var(--surface-muted);
}
.block {
  display: grid;
  gap: 10px;
  padding: 12px 14px;
  border: 1px solid var(--line);
  border-radius: 0.75rem;
  background: var(--surface);
  box-shadow: var(--shadow-card);
  flex-shrink: 0;
}
.block-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
.block-title {
  font-size: 0.78rem;
  font-weight: 600;
  letter-spacing: 0.04em;
  color: var(--ink-muted);
}
.block-head-actions {
  display: inline-flex;
  gap: 6px;
}
.ghost.sm {
  padding: 4px 9px;
  font-size: 0.78rem;
  border-radius: 0.4rem;
}
.row.group-row,
.row.add-row {
  display: flex;
  align-items: center;
}
.row.group-row select,
.row.group-row input,
.row.add-row input {
  flex: 1 1 0;
  min-width: 0;
}
.row.group-row button,
.row.add-row button {
  flex-shrink: 0;
}
.left .table-wrap {
  flex: 1;
  min-height: 0;
  max-height: none;
}
.row {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 8px;
}
.batch-bar {
  grid-template-columns: auto 1fr auto auto;
  align-items: end;
  padding: 8px 10px;
  border: 1px solid var(--line);
  border-radius: 0.75rem;
  background: var(--surface-muted);
}
.batch-count {
  align-self: center;
  font-size: 0.85rem;
  white-space: nowrap;
}
.check-col {
  width: 32px;
  text-align: center;
  padding-left: 8px;
  padding-right: 4px;
}
.check-col input[type='checkbox'] {
  cursor: pointer;
}
.auto {
  display: flex;
  gap: 6px;
  align-items: center;
  color: var(--muted);
  font-size: 0.8rem;
}
label:not(.auto) {
  display: grid;
  gap: 6px;
  font-size: 0.8rem;
  color: var(--muted);
}
input,
select {
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: 0.5rem;
  color: var(--text);
  padding: 8px 10px;
}
.primary {
  background: var(--accent);
  color: var(--brand-foreground);
  border: none;
  border-radius: 0.5rem;
  padding: 8px 12px;
  font-weight: 600;
}
.ghost,
.chip {
  background: transparent;
  border: 1px solid var(--border);
  color: var(--text);
  border-radius: 0.5rem;
  padding: 8px 12px;
}
.ghost.on {
  border-color: var(--brand, var(--accent));
  color: var(--text);
}
.col-prefs-panel {
  display: flex;
  flex-wrap: wrap;
  gap: 10px 14px;
  padding: 8px 0;
  font-size: 0.85rem;
  color: var(--muted);
}
.col-pref-item {
  display: flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
}
.chip {
  padding: 4px 8px;
  font-size: 0.75rem;
  color: var(--muted);
}
.chip.on {
  background: var(--brand-light);
  color: var(--brand);
  border-color: var(--brand-soft);
  font-weight: 500;
}
.limits {
  display: flex;
  gap: 4px;
}
.link {
  background: none;
  border: none;
  color: var(--muted);
  padding: 0;
}
.link:hover {
  color: var(--danger);
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
.muted {
  color: var(--muted);
  font-size: 0.85rem;
}
.suspend-tag {
  margin-left: 4px;
  font-size: 0.7rem;
  padding: 0 4px;
  border-radius: 0.25rem;
  border: 1px solid var(--border);
  color: var(--danger, #b42318);
}
.table-wrap {
  border: 1px solid var(--line);
  border-radius: 0.75rem;
  overflow: auto;
  background: var(--surface);
  box-shadow: var(--shadow-card);
  max-height: 320px;
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
th.sortable {
  cursor: pointer;
  user-select: none;
}
th.sortable:hover {
  color: var(--text);
}
tbody tr {
  cursor: pointer;
}
tbody tr:hover td {
  background: var(--surface-muted);
}
tbody tr.on td {
  background: var(--brand-light);
}
tbody tr.on:hover td {
  background: var(--brand-light);
}
tbody tr.off-plan td {
  background: #fee2e2;
}
tbody tr.off-plan.on td {
  background: var(--brand-light);
}
.warn {
  color: var(--danger);
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
  padding: 24px !important;
}
.chart-head {
  display: flex;
  gap: 12px 16px;
  align-items: center;
  flex-wrap: wrap;
  padding: 14px 16px;
  border: 1px solid var(--line);
  border-radius: 0.75rem;
  background: var(--surface);
  box-shadow: var(--shadow-card);
}
.quote-id {
  display: grid;
  gap: 3px;
  min-width: 0;
}
.quote-name {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 1rem;
  font-weight: 600;
}
.quote-meta {
  display: flex;
  gap: 6px;
  font-size: 0.75rem;
}
.quote-price {
  display: flex;
  align-items: baseline;
  gap: 10px;
  margin-left: auto;
}
.quote-price .price {
  font-size: 1.6rem;
  font-weight: 700;
  line-height: 1;
  font-variant-numeric: tabular-nums;
}
.quote-price .change {
  font-size: 0.9rem;
  font-weight: 600;
}
.quote-price.up {
  color: var(--danger);
}
.quote-price.down {
  color: var(--ok);
}
.chart {
  border: 1px solid var(--line);
  border-radius: 0.75rem;
  background: var(--surface);
  box-shadow: var(--shadow-card);
  padding: 12px;
}
.bar-meta {
  margin-top: 4px;
}
.mini {
  max-height: 220px;
}
.fund-card {
  display: grid;
  gap: 10px;
  padding: 12px 14px;
  border: 1px solid var(--border);
  border-radius: 0.75rem;
  background: var(--bg-elevated);
}
.fund-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
.fund-head h3 {
  margin: 0;
  font-size: 0.9rem;
  font-weight: 600;
}
.fund-block {
  display: grid;
  gap: 8px;
}
.fund-block h4 {
  margin: 0;
  font-size: 0.85rem;
  font-weight: 600;
}
.fund-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px 12px;
  margin: 0;
}
.fund-grid dt {
  color: var(--muted);
  font-size: 0.75rem;
}
.fund-grid dd {
  margin: 2px 0 0;
  font-size: 0.85rem;
}
.fund-disc {
  width: 100%;
  border-collapse: collapse;
}
.fund-disc th,
.fund-disc td {
  padding: 6px 8px;
  border-bottom: 1px solid var(--border);
  font-size: 0.8rem;
  text-align: left;
}
@media (max-width: 900px) {
  .workspace {
    grid-template-columns: 1fr;
  }
  .left {
    border-right: none;
    border-bottom: 1px solid var(--border);
  }
}
</style>

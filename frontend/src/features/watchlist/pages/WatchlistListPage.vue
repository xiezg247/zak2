<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import AppShell from '../../../components/AppShell.vue'
import BarsChartModal from '../../../components/BarsChartModal.vue'
import FundamentalsModal from '../../../components/FundamentalsModal.vue'
import StockAnalysisModal from '../../analysis/components/StockAnalysisModal.vue'
import { confirmDialog, promptDialog } from '../../../lib/dialog'
import { cmpNullable } from '../../../lib/sort'
import {
  watchlistApi,
  type GroupMembersBatchResult,
  type WatchlistGroup,
  type WatchlistItem,
} from '../../../api/watchlist'
import { usePolling } from '../../../composables/usePolling'
import { POLL_FAST_MS, POLL_SLOW_MS, useQuoteNotify } from '../../../composables/useQuoteNotify'
import { useStockAnalysis } from '../../analysis/composables/useStockAnalysis'
import WatchlistBatchBar from '../components/WatchlistBatchBar.vue'
import WatchlistGroupsBar from '../components/WatchlistGroupsBar.vue'
import WatchlistListToolbar from '../components/WatchlistListToolbar.vue'
import WatchlistQuoteTable from '../components/WatchlistQuoteTable.vue'

const analysis = useStockAnalysis()

const route = useRoute()

const items = ref<WatchlistItem[]>([])
const groups = ref<WatchlistGroup[]>([])
const groupId = ref<string>('')
const addSymbol = ref('')
const error = ref('')
const loading = ref(false)
const autoRefresh = ref(true)
const lastRefresh = ref('')

const chartVt = ref('')
const fundVt = ref('')

const chartName = computed(
  () => items.value.find((i) => i.vt_symbol === chartVt.value)?.name || '',
)
const fundName = computed(
  () => items.value.find((i) => i.vt_symbol === fundVt.value)?.name || '',
)

const { connected } = useQuoteNotify({
  onQuotesUpdated: () => {
    if (!autoRefresh.value || document.hidden) return
    void refresh(true)
  },
})

function tick() {
  if (!autoRefresh.value) return
  if (document.hidden) return
  void refresh(true)
}

usePolling(
  tick,
  () => (connected.value ? POLL_SLOW_MS : POLL_FAST_MS),
  [connected],
)

const subtitle = computed(() => {
  const n = items.value.length
  const g = groupId.value ? groups.value.find((x) => x.id === groupId.value) : null
  const ts = lastRefresh.value ? ` · ${lastRefresh.value}` : ''
  return g ? `${n} 只 · ${g.name}${ts}` : `${n} 只自选${ts}`
})

type SortKey = 'last_price' | 'change_pct' | 'turnover_rate' | 'amount' | null

const listFilter = ref('')
const sortKey = ref<SortKey>(null)
const sortDir = ref<'asc' | 'desc'>('desc')
const checked = ref<Set<string>>(new Set())
const batchTargetGroupId = ref('')
const batchMsg = ref('')

const COL_PREFS_KEY = 'zak2:watchlist:list_columns'

type OptionalCol = 'industry' | 'turnover_rate' | 'amount'

const DEFAULT_COL_VISIBLE: Record<OptionalCol, boolean> = {
  industry: true,
  turnover_rate: true,
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

const tableColspan = computed(() => {
  let n = 7
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

const checkedVts = computed(() => [...checked.value])

const allDisplayedChecked = computed(() => {
  const rows = displayedItems.value
  if (!rows.length) return false
  return rows.every((r) => checked.value.has(r.vt_symbol))
})

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
  } catch (e) {
    error.value = e instanceof Error ? e.message : '加载失败'
  } finally {
    loading.value = false
  }
}

function openChart(item: WatchlistItem) {
  chartVt.value = item.vt_symbol
}

function openFund(item: WatchlistItem) {
  fundVt.value = item.vt_symbol
}

function openAnalyze(item: WatchlistItem) {
  analysis.open(item.vt_symbol, item.name)
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
    if (chartVt.value === item.vt_symbol) chartVt.value = ''
    if (fundVt.value === item.vt_symbol) fundVt.value = ''
    await refresh()
  } catch (e) {
    error.value = e instanceof Error ? e.message : '删除失败'
  }
}

async function onCreateGroup(name: string) {
  const n = name.trim()
  if (!n) return
  try {
    await watchlistApi.createGroup(n)
    await refresh()
  } catch (e) {
    error.value = e instanceof Error ? e.message : '创建分组失败'
  }
}

function selectGroup(id: string) {
  if (groupId.value === id) return
  groupId.value = id
  void refresh()
}

async function onRenameGroup(id: string) {
  const cur = groups.value.find((g) => g.id === id)
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
    await watchlistApi.renameGroup(id, name)
    await refresh()
  } catch (e) {
    error.value = e instanceof Error ? e.message : '改名失败'
  }
}

async function onDeleteGroup(id: string) {
  const ok = await confirmDialog({
    title: '删除分组',
    message: '确定删除该分组？自选标的不会被删除',
    danger: true,
  })
  if (!ok) return
  try {
    error.value = ''
    await watchlistApi.deleteGroup(id)
    if (groupId.value === id) {
      groupId.value = ''
      checked.value = new Set()
    }
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

watch(groupId, () => {
  checked.value = new Set()
  batchTargetGroupId.value = ''
  batchMsg.value = ''
})

onMounted(async () => {
  loadColPrefs()
  await refresh(false)
  const q = String(route.query.symbol || '').trim()
  if (q) {
    const hit = items.value.find((i) => i.vt_symbol === q || i.tf_symbol === q)
    if (hit) openChart(hit)
    else {
      try {
        await watchlistApi.add(q)
        await refresh(true)
        const added = items.value.find((i) => i.vt_symbol.includes(q.split('.')[0]))
        if (added) openChart(added)
      } catch {
        /* ignore */
      }
    }
  }
})
</script>

<template>
  <AppShell title="自选" :subtitle="subtitle" active="watchlist-list">
    <div class="page">
      <WatchlistGroupsBar
        :groups="groups"
        :group-id="groupId"
        v-model:auto-refresh="autoRefresh"
        :loading="loading"
        :connected="connected"
        @select="selectGroup"
        @create="onCreateGroup"
        @rename="onRenameGroup"
        @delete="onDeleteGroup"
        @move="onMoveGroup"
        @refresh="refresh()"
      />

      <WatchlistListToolbar
        v-model:add-symbol="addSymbol"
        v-model:list-filter="listFilter"
        v-model:columns-open="columnsOpen"
        :sort-key="sortKey"
        :col-visible="colVisible"
        :displayed-count="displayedItems.length"
        @add="onAdd"
        @clear-sort="clearSort"
        @set-col-visible="setColVisible"
      />

      <p v-if="error" class="err">{{ error }}</p>
      <p v-else-if="batchMsg" class="muted">{{ batchMsg }}</p>
      <p v-if="loading" class="muted">刷新中…</p>

      <WatchlistBatchBar
        v-if="hasChecked"
        v-model:batch-target-group-id="batchTargetGroupId"
        :checked-count="checked.size"
        :other-groups="otherGroups"
        :group-id="groupId"
        @batch-add="onBatchAddToGroup"
        @batch-remove="onBatchRemoveFromGroup"
      />

      <WatchlistQuoteTable
        :rows="displayedItems"
        :total-count="items.length"
        :col-visible="colVisible"
        :checked-vts="checkedVts"
        :all-displayed-checked="allDisplayedChecked"
        :sort-key="sortKey"
        :sort-dir="sortDir"
        :table-colspan="tableColspan"
        @toggle-sort="toggleSort"
        @toggle-checked="toggleChecked"
        @toggle-all="toggleAllDisplayed"
        @chart="openChart"
        @fund="openFund"
        @analyze="openAnalyze"
        @remove="onRemove"
      />
    </div>

    <BarsChartModal v-model:vt="chartVt" :name="chartName" />
    <FundamentalsModal v-model:vt="fundVt" :name="fundName" />
  </AppShell>
  <StockAnalysisModal />
</template>

<style scoped>
.page {
  display: grid;
  gap: 14px;
  padding: 16px 24px 24px;
}
.err {
  margin: 0;
  color: var(--danger);
  font-size: 0.85rem;
}
.muted {
  color: var(--muted);
  font-size: 0.85rem;
}
</style>

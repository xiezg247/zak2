<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import AppShell from '../../../components/AppShell.vue'
import BarsChartModal from '../../../components/BarsChartModal.vue'
import FundamentalsModal from '../../../components/FundamentalsModal.vue'
import StockAnalysisModal from '../../../components/StockAnalysisModal.vue'
import { confirmDialog, promptDialog } from '../../../lib/dialog'
import { formatAmountYi, formatNum2, formatPrice } from '../../../lib/format'
import { cmpNullable } from '../../../lib/sort'
import {
  watchlistApi,
  type GroupMembersBatchResult,
  type WatchlistGroup,
  type WatchlistItem,
} from '../../../api/watchlist'
import { usePolling } from '../../../composables/usePolling'
import { POLL_FAST_MS, POLL_SLOW_MS, useQuoteNotify } from '../../../composables/useQuoteNotify'
import { useStockAnalysis } from '../../../composables/useStockAnalysis'

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

const optionalColLabels: { key: OptionalCol; label: string }[] = [
  { key: 'industry', label: '行业' },
  { key: 'turnover_rate', label: '换手%' },
  { key: 'amount', label: '成交额' },
]

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
      <div class="group-bar">
          <div class="group-chips">
            <button
              type="button"
              class="group-chip"
              :class="{ on: !groupId }"
              @click="selectGroup('')"
            >
              全部自选
            </button>
            <span
              v-for="g in groups"
              :key="g.id"
              class="group-chip-wrap"
              :class="{ on: groupId === g.id }"
            >
              <button type="button" class="group-chip" @click="selectGroup(g.id)">
                {{ g.name }}
              </button>
              <span class="group-chip-ops">
                <button
                  type="button"
                  class="chip-op"
                  title="改名"
                  @click.stop="onRenameGroup(g.id)"
                >
                  <svg
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    stroke-width="2"
                    stroke-linecap="round"
                    stroke-linejoin="round"
                  >
                    <path
                      d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z"
                    />
                  </svg>
                </button>
                <button
                  type="button"
                  class="chip-op danger"
                  title="删除分组"
                  @click.stop="onDeleteGroup(g.id)"
                >
                  <svg
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    stroke-width="2"
                    stroke-linecap="round"
                    stroke-linejoin="round"
                  >
                    <path
                      d="M3 6h18M8 6V4a1 1 0 011-1h6a1 1 0 011 1v2m3 0v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6h14zM10 11v6M14 11v6"
                    />
                  </svg>
                </button>
              </span>
            </span>
            <span class="group-add">
              <input v-model="newGroup" placeholder="新分组名" @keyup.enter="onCreateGroup" />
              <button type="button" class="ghost" @click="onCreateGroup">建组</button>
            </span>
            <button
              v-if="groupId"
              type="button"
              class="ghost"
              :disabled="groupIndex <= 0"
              @click="onMoveGroup(-1)"
            >
              上移
            </button>
            <button
              v-if="groupId"
              type="button"
              class="ghost"
              :disabled="groupIndex < 0 || groupIndex >= groups.length - 1"
              @click="onMoveGroup(1)"
            >
              下移
            </button>
          </div>
          <div class="actions">
            <label class="auto">
              <input v-model="autoRefresh" type="checkbox" />
              {{ connected ? 'WS 推送 + 慢轮询' : '每 15s 刷新行情' }}
            </label>
            <button type="button" class="ghost" :disabled="loading" @click="refresh()">刷新</button>
          </div>
        </div>

        <div class="toolbar">
          <div class="tabs">
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
          <div class="actions">
            <span class="muted count-hint">{{ displayedItems.length }} 只</span>
          </div>
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

        <p v-if="error" class="err">{{ error }}</p>
        <p v-else-if="batchMsg" class="muted">{{ batchMsg }}</p>
        <p v-if="loading" class="muted">刷新中…</p>

        <div v-if="hasChecked" class="batch-bar">
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
                <th>#</th>
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
                <th v-if="colVisible.amount" class="sortable" @click="toggleSort('amount')">
                  成交额{{ sortMark('amount') }}
                </th>
                <th class="ops">操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(item, idx) in displayedItems" :key="item.vt_symbol">
                <td class="check-col" @click.stop>
                  <input
                    type="checkbox"
                    :checked="checked.has(item.vt_symbol)"
                    @change="toggleChecked(item.vt_symbol)"
                  />
                </td>
                <td>
                  <span class="rank-badge">{{ idx + 1 }}</span>
                </td>
                <td class="mono">{{ item.vt_symbol }}</td>
                <td>
                  {{ item.name || '—' }}
                  <span v-if="item.suspended" class="suspend-tag" title="停牌">停</span>
                </td>
                <td v-if="colVisible.industry">
                  {{ item.industry?.trim() ? item.industry : '—' }}
                </td>
                <td>{{ formatPrice(item.last_price) }}</td>
                <td
                  :class="{
                    up: (item.change_pct || 0) > 0,
                    down: (item.change_pct || 0) < 0,
                  }"
                >
                  {{ formatNum2(item.change_pct) }}
                </td>
                <td v-if="colVisible.turnover_rate">{{ formatNum2(item.turnover_rate) }}</td>
                <td v-if="colVisible.amount">{{ formatAmountYi(item.amount) }}</td>
                <td class="ops">
                  <div class="row-ops">
                    <button type="button" class="icon-btn" title="K线" @click="openChart(item)">
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
                      title="基本面"
                      @click="openFund(item)"
                    >
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
                      @click.stop="analysis.open(item.vt_symbol, item.name)"
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
                    <button
                      type="button"
                      class="icon-btn danger"
                      title="删除"
                      @click="onRemove(item)"
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
                          d="M3 6h18M8 6V4a1 1 0 011-1h6a1 1 0 011 1v2m3 0v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6h14zM10 11v6M14 11v6"
                        />
                      </svg>
                    </button>
                  </div>
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
.group-bar {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
  flex-wrap: wrap;
  padding: 8px 10px;
  border: 1px solid var(--line);
  border-radius: 0.75rem;
  background: var(--surface);
  box-shadow: var(--shadow-card);
}
.group-chips {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  align-items: center;
}
.group-chip-wrap {
  position: relative;
  display: inline-flex;
  align-items: center;
  border: 1px solid var(--border);
  border-radius: 0.5rem;
  background: var(--bg);
  transition:
    border-color 0.15s,
    background 0.15s;
}
.group-chip {
  background: none;
  border: none;
  color: var(--text);
  padding: 5px 10px;
  font-size: 0.85rem;
  cursor: pointer;
  border-radius: inherit;
}
.group-chip:hover {
  color: var(--brand);
}
.group-chip-wrap.on {
  background: var(--brand-light);
  border-color: var(--brand-soft);
}
.group-chip-wrap.on .group-chip {
  color: var(--brand);
  font-weight: 600;
}
.group-chip-ops {
  display: none;
  align-items: center;
  gap: 1px;
  padding-right: 4px;
}
.group-chip-wrap:hover .group-chip-ops {
  display: inline-flex;
}
.group-chip-wrap:hover .group-chip {
  padding-right: 2px;
}
.chip-op {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: none;
  border: none;
  color: var(--muted);
  padding: 3px;
  border-radius: 0.3rem;
  cursor: pointer;
}
.chip-op:hover {
  color: var(--brand);
  background: var(--surface-muted);
}
.chip-op.danger:hover {
  color: var(--danger);
}
.chip-op svg {
  width: 12px;
  height: 12px;
}
.group-add {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.group-add input {
  min-width: 120px;
  padding: 5px 10px;
  font-size: 0.85rem;
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
.actions label.auto {
  white-space: nowrap;
}
input,
select {
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: 0.5rem;
  color: var(--text);
  padding: 6px 10px;
}
.tabs input {
  min-width: 150px;
}
.ghost,
.primary {
  border-radius: 0.5rem;
  padding: 6px 10px;
  border: 1px solid var(--border);
  cursor: pointer;
}
.ghost {
  background: transparent;
  color: var(--text);
}
.ghost:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}
.ghost.on {
  border-color: var(--brand, #333);
  color: var(--text);
  font-weight: 500;
}
.primary {
  background: var(--accent);
  border-color: transparent;
  color: var(--brand-foreground);
  font-weight: 600;
}
.auto {
  display: flex;
  gap: 6px;
  align-items: center;
  color: var(--muted);
  font-size: 0.8rem;
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
.count-hint {
  font-size: 0.8rem;
  font-variant-numeric: tabular-nums;
}
.col-prefs-panel {
  display: flex;
  flex-wrap: wrap;
  gap: 10px 14px;
  padding: 8px 12px;
  font-size: 0.85rem;
  color: var(--muted);
  background: var(--bg-elevated);
  border: 1px solid var(--line);
  border-radius: 0.75rem;
}
.col-pref-item {
  display: flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
}
.batch-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  padding: 8px 12px;
  border: 1px solid var(--line);
  border-radius: 0.75rem;
  background: var(--surface-muted);
}
.batch-bar label {
  display: flex;
  gap: 6px;
  align-items: center;
  font-size: 0.8rem;
  color: var(--muted);
}
.batch-count {
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
.table-wrap {
  border: 1px solid var(--line);
  border-radius: 0.75rem;
  background: var(--surface);
  box-shadow: var(--shadow-card);
  overflow: auto;
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
  background: var(--surface-muted);
  position: sticky;
  top: 0;
  font-weight: 500;
}
th.sortable {
  cursor: pointer;
  user-select: none;
}
th.sortable:hover {
  color: var(--text);
}
tbody tr:hover td {
  background: var(--surface-muted);
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
.icon-btn.danger:hover {
  border-color: var(--danger);
  color: var(--danger);
}
.icon-btn svg {
  width: 15px;
  height: 15px;
}
.row-ops {
  display: flex;
  gap: 4px;
}
th.ops,
td.ops {
  text-align: right;
}
.suspend-tag {
  margin-left: 4px;
  font-size: 0.7rem;
  padding: 0 4px;
  border-radius: 0.25rem;
  border: 1px solid var(--border);
  color: var(--danger, #b42318);
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
  padding: 28px !important;
}
.draft-link {
  color: var(--brand);
  margin-left: 4px;
}
</style>

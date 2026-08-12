<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import AppShell from '../components/AppShell.vue'
import CandleChart from '../components/CandleChart.vue'
import {
  watchlistApi,
  type Bar,
  type NotifyLogItem,
  type PlanSymbolStatus,
  type PositionItem,
  type StrategyBoard,
  type WatchlistGroup,
  type WatchlistItem,
} from '../api/watchlist'
import { POLL_FAST_MS, POLL_SLOW_MS, useQuoteNotify } from '../composables/useQuoteNotify'

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
const barLimit = ref(90)
const lastRefresh = ref('')
const board = ref<StrategyBoard | null>(null)
const boardError = ref('')
const positions = ref<PositionItem[]>([])
const posError = ref('')
const posMsg = ref('')
const editingVt = ref('')
const signalAdd = ref('')
const signalError = ref('')
const signalMsg = ref('')
const riskForm = ref({
  total_capital: '',
  stop_loss_pct: '',
  caution_float_pct: '',
})
const prefsReady = ref(false)
const riskError = ref('')
const riskMsg = ref('')
const riskSaving = ref(false)
const showOffPlanChips = ref(false)
const notifyOpen = ref(false)
const notifyLoaded = ref(false)
const notifyLoading = ref(false)
const notifyError = ref('')
const notifyItems = ref<NotifyLogItem[]>([])
const notifyExpandedId = ref('')
const form = ref({
  symbol: '',
  cost_price: '',
  volume: '100',
  buy_date: new Date().toISOString().slice(0, 10),
  notes: '',
})
let timer: number | undefined
let boardTimer: number | undefined

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

const panelSymbols = computed(() => board.value?.panel_symbols || [])
const panelMax = 10
const riskSummary = computed(() => board.value?.risk_summary ?? null)
const planSymbols = computed(() => riskSummary.value?.plan_symbols ?? [])

function planSymbolLabel(row: PlanSymbolStatus): string {
  if (row.in_position) return '持仓'
  if (row.in_watchlist) return '自选'
  return '仅计划'
}

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

function formatAmountYi(v: number | null | undefined): string {
  if (v == null || Number.isNaN(v)) return '—'
  return `${(v / 1e8).toFixed(2)}亿`
}

function formatNum2(v: number | null | undefined): string {
  if (v == null || Number.isNaN(v)) return '—'
  return v.toFixed(2)
}

function cmpNullable(a: number | null | undefined, b: number | null | undefined, dir: 'asc' | 'desc'): number {
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

function applyRiskPrefs(prefs: {
  total_capital: number | null
  stop_loss_pct: number
  caution_float_pct: number
}) {
  riskForm.value = {
    total_capital: prefs.total_capital != null ? String(prefs.total_capital) : '',
    stop_loss_pct: String(Number((prefs.stop_loss_pct * 100).toFixed(4))),
    caution_float_pct: String(prefs.caution_float_pct),
  }
  prefsReady.value = true
}

function formatPctRatio(v: number | null | undefined): string {
  if (v == null || Number.isNaN(v)) return '—'
  return `${(v * 100).toFixed(1)}%`
}

function formatMarketValue(v: number | null | undefined): string {
  if (v == null || Number.isNaN(v)) return '—'
  return v.toLocaleString()
}

function toggleOffPlanChips() {
  if (!riskSummary.value || riskSummary.value.off_plan_count <= 0) return
  showOffPlanChips.value = !showOffPlanChips.value
}

async function refreshBoard(quiet = false) {
  if (!quiet) boardError.value = ''
  const loadPrefs = !quiet || !prefsReady.value
  try {
    const [b, pos, prefs] = await Promise.all([
      watchlistApi.strategyBoard(),
      watchlistApi.listPositions(),
      loadPrefs ? watchlistApi.tradingRisk() : Promise.resolve(null),
    ])
    board.value = b
    positions.value = pos
    if (prefs) applyRiskPrefs(prefs)
  } catch (e) {
    boardError.value = e instanceof Error ? e.message : '策略看板加载失败'
  }
}

async function saveTradingRisk() {
  if (!prefsReady.value) return
  riskError.value = ''
  riskMsg.value = ''
  const capitalRaw = riskForm.value.total_capital.trim()
  const stopRaw = Number(riskForm.value.stop_loss_pct)
  const cautionRaw = Number(riskForm.value.caution_float_pct)
  if (capitalRaw && !(Number(capitalRaw) > 0)) {
    riskError.value = '总资金须为空或大于 0'
    return
  }
  if (!(stopRaw > 0) || stopRaw > 50) {
    riskError.value = '止损%须在 (0, 50] 范围内'
    return
  }
  if (!(cautionRaw < 0)) {
    riskError.value = '浮亏警戒须为负数（如 -5）'
    return
  }
  riskSaving.value = true
  try {
    const prefs = await watchlistApi.putTradingRisk({
      total_capital: capitalRaw ? Number(capitalRaw) : null,
      stop_loss_pct: stopRaw / 100,
      caution_float_pct: cautionRaw,
    })
    applyRiskPrefs(prefs)
    riskMsg.value = '风控偏好已保存'
    await refreshBoard()
  } catch (e) {
    riskError.value = e instanceof Error ? e.message : '保存失败'
  } finally {
    riskSaving.value = false
  }
}

function prettyPayload(payload: Record<string, unknown>): string {
  try {
    return JSON.stringify(payload, null, 2)
  } catch {
    return String(payload)
  }
}

function notifyStatusClass(status: string): string {
  const s = status.trim().toLowerCase()
  if (s === 'ok' || s === 'success') return ''
  return 'warn'
}

async function loadNotifyLog() {
  notifyLoading.value = true
  notifyError.value = ''
  try {
    const out = await watchlistApi.notifyLog()
    notifyItems.value = out.items
    notifyLoaded.value = true
  } catch (e) {
    notifyError.value = e instanceof Error ? e.message : '通知历史加载失败'
  } finally {
    notifyLoading.value = false
  }
}

function toggleNotifyOpen() {
  notifyOpen.value = !notifyOpen.value
  if (notifyOpen.value && !notifyLoaded.value) {
    void loadNotifyLog()
  }
}

function toggleNotifyRow(id: string) {
  notifyExpandedId.value = notifyExpandedId.value === id ? '' : id
}

function resetPosForm() {
  editingVt.value = ''
  form.value = {
    symbol: selected.value?.vt_symbol || '',
    cost_price: selected.value?.last_price != null ? selected.value.last_price.toFixed(2) : '',
    volume: '100',
    buy_date: new Date().toISOString().slice(0, 10),
    notes: '',
  }
  posMsg.value = ''
  posError.value = ''
}

function fillPosForm(row: PositionItem) {
  editingVt.value = row.vt_symbol
  form.value = {
    symbol: row.vt_symbol,
    cost_price: String(row.cost_price),
    volume: String(row.volume),
    buy_date: row.buy_date.slice(0, 10),
    notes: row.notes || '',
  }
  posMsg.value = ''
  posError.value = ''
}

function editBoardPosition(row: { vt_symbol: string; cost_price: number; volume: number; buy_date: string }) {
  const full = positions.value.find((p) => p.vt_symbol === row.vt_symbol)
  if (full) {
    fillPosForm(full)
    return
  }
  fillPosForm({
    symbol: row.vt_symbol.split('.')[0] || row.vt_symbol,
    exchange: row.vt_symbol.split('.')[1] || 'SSE',
    vt_symbol: row.vt_symbol,
    cost_price: row.cost_price,
    volume: row.volume,
    buy_date: row.buy_date,
    notes: '',
    source: 'manual',
    plan_pct: null,
    sort_order: 0,
    created_at: '',
    updated_at: '',
  })
}

async function savePosition() {
  posError.value = ''
  posMsg.value = ''
  const symbol = form.value.symbol.trim() || selected.value?.vt_symbol || ''
  const cost = Number(form.value.cost_price)
  const volume = Number(form.value.volume)
  if (!symbol) {
    posError.value = '请填写代码（须已在自选）'
    return
  }
  if (!(cost > 0) || !(volume > 0)) {
    posError.value = '成本价与数量须大于 0'
    return
  }
  const body = {
    symbol,
    cost_price: cost,
    volume,
    buy_date: form.value.buy_date,
    notes: form.value.notes.trim(),
  }
  try {
    if (editingVt.value) {
      await watchlistApi.updatePosition(editingVt.value, body)
      posMsg.value = '已更新持仓'
    } else {
      await watchlistApi.addPosition(body)
      posMsg.value = '已录入持仓'
    }
    resetPosForm()
    await refreshBoard()
  } catch (e) {
    posError.value = e instanceof Error ? e.message : '保存失败'
  }
}

async function removePosition(vt: string) {
  posError.value = ''
  try {
    await watchlistApi.removePosition(vt)
    if (editingVt.value === vt) resetPosForm()
    posMsg.value = '已删除持仓'
    await refreshBoard()
  } catch (e) {
    posError.value = e instanceof Error ? e.message : '删除失败'
  }
}

function useSelectedForPos() {
  if (!selected.value) return
  form.value.symbol = selected.value.vt_symbol
  if (selected.value.last_price != null && !form.value.cost_price) {
    form.value.cost_price = selected.value.last_price.toFixed(2)
  }
}

async function addToSignalPanel(raw?: string) {
  signalError.value = ''
  signalMsg.value = ''
  const symbol = (raw || signalAdd.value || selected.value?.vt_symbol || '').trim()
  if (!symbol) {
    signalError.value = '请填写代码或先选中自选'
    return
  }
  try {
    await watchlistApi.addSignalPanelMember(symbol)
    signalAdd.value = ''
    signalMsg.value = `已加入信号名单：${symbol}`
    await refreshBoard()
  } catch (e) {
    signalError.value = e instanceof Error ? e.message : '加入失败'
  }
}

async function removeFromSignalPanel(vt: string) {
  signalError.value = ''
  try {
    await watchlistApi.removeSignalPanelMember(vt)
    signalMsg.value = `已移出信号名单：${vt}`
    await refreshBoard()
  } catch (e) {
    signalError.value = e instanceof Error ? e.message : '移除失败'
  }
}

async function refresh(quiet = false, skipBoard = false) {
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
    if (!skipBoard) void refreshBoard(true)
  } catch (e) {
    error.value = e instanceof Error ? e.message : '加载失败'
  } finally {
    loading.value = false
  }
}

async function loadBars() {
  barsError.value = ''
  bars.value = []
  if (!selected.value) return
  try {
    const resp = await watchlistApi.bars(selected.value.vt_symbol, 'd', barLimit.value)
    bars.value = resp.bars
  } catch (e) {
    barsError.value = e instanceof Error ? e.message : '无 K 线'
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
  const next = window.prompt('新分组名', cur?.name || '')
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
  if (!window.confirm('确定删除该分组？自选标的不会被删除')) return
  try {
    error.value = ''
    await watchlistApi.deleteGroup(groupId.value)
    groupId.value = ''
    await refresh()
  } catch (e) {
    error.value = e instanceof Error ? e.message : '删组失败'
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

function selectVt(vt: string) {
  const hit = items.value.find((i) => i.vt_symbol === vt)
  if (hit) {
    selected.value = hit
    return
  }
  // 不在自选：仍可尝试用代码打开 K 线（走 query 添加逻辑外的直接 bars）
  selected.value = {
    symbol: vt.split('.')[0] || vt,
    exchange: vt.split('.')[1] || 'SSE',
    name: '',
    sort_order: 0,
    vt_symbol: vt,
    tf_symbol: vt,
    last_price: null,
    change_pct: null,
    turnover_rate: null,
    volume: null,
    amount: null,
    volume_ratio: null,
  }
}

function signalClass(sig: string) {
  if (sig === 'buy') return 'up'
  if (sig === 'sell') return 'down'
  return ''
}

function tick() {
  if (!autoRefresh.value) return
  if (document.hidden) return
  void refresh(true)
}

function tickBoard() {
  if (document.hidden) return
  void refreshBoard(true)
}

watch(selected, () => {
  void loadBars()
})

watch(barLimit, () => {
  void loadBars()
})

onMounted(async () => {
  await refresh(false, true)
  await refreshBoard()
  const q = String(route.query.symbol || '').trim()
  if (q) {
    const hit = items.value.find((i) => i.vt_symbol === q || i.tf_symbol === q)
    if (hit) selected.value = hit
    else {
      try {
        await watchlistApi.add(q)
        await refresh(true, true)
        selected.value = items.value.find((i) => i.vt_symbol.includes(q.split('.')[0])) || selected.value
      } catch {
        /* ignore */
      }
    }
  }
  timer = window.setInterval(tick, connected.value ? POLL_SLOW_MS : POLL_FAST_MS)
  boardTimer = window.setInterval(tickBoard, 45000)
})

onUnmounted(() => {
  if (timer) window.clearInterval(timer)
  if (boardTimer) window.clearInterval(boardTimer)
})
</script>

<template>
  <AppShell title="自选" :subtitle="subtitle" active="watchlist">
    <div class="page">
      <div class="workspace">
        <section class="left">
          <div class="block">
            <label>
              分组
              <select v-model="groupId" @change="refresh()">
                <option value="">全部自选</option>
                <option v-for="g in groups" :key="g.id" :value="g.id">{{ g.name }}</option>
              </select>
            </label>
            <div class="row">
              <input v-model="newGroup" placeholder="新分组名" @keyup.enter="onCreateGroup" />
              <button type="button" class="ghost" @click="onCreateGroup">建组</button>
            </div>
            <div v-if="groupId" class="row">
              <button type="button" class="ghost" @click="onRenameGroup">改名</button>
              <button type="button" class="ghost" @click="onDeleteGroup">删组</button>
            </div>
            <div v-if="groupId && selected" class="row">
              <button type="button" class="ghost" @click="onAddToGroup">加入此组</button>
              <button type="button" class="ghost" @click="onRemoveFromGroup">移出此组</button>
            </div>
          </div>

          <div class="block">
            <div class="row">
              <input
                v-model="addSymbol"
                placeholder="600519.SSE / 000001"
                @keyup.enter="onAdd"
              />
              <button type="button" class="primary" @click="onAdd">添加</button>
            </div>
            <label class="auto">
              <input v-model="autoRefresh" type="checkbox" />
              {{ connected ? 'WS 推送 + 慢轮询' : '每 15s 刷新行情' }}
            </label>
            <div class="row">
              <input v-model="listFilter" placeholder="过滤代码/名称" />
              <button
                v-if="sortKey"
                type="button"
                class="ghost"
                @click="clearSort"
              >
                默认序
              </button>
            </div>
          </div>

          <p v-if="error" class="err">{{ error }}</p>
          <p v-if="loading" class="muted">刷新中…</p>

          <div class="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>代码</th>
                  <th>名称</th>
                  <th>行业</th>
                  <th class="sortable" @click="toggleSort('last_price')">现价{{ sortMark('last_price') }}</th>
                  <th class="sortable" @click="toggleSort('change_pct')">涨幅%{{ sortMark('change_pct') }}</th>
                  <th class="sortable" @click="toggleSort('turnover_rate')">换手%{{ sortMark('turnover_rate') }}</th>
                  <th class="sortable" @click="toggleSort('volume_ratio')">量比{{ sortMark('volume_ratio') }}</th>
                  <th class="sortable" @click="toggleSort('amount')">成交额{{ sortMark('amount') }}</th>
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
                  <td class="mono">{{ item.vt_symbol }}</td>
                  <td>{{ item.name || '—' }}</td>
                  <td>{{ item.industry?.trim() ? item.industry : '—' }}</td>
                  <td>{{ formatNum2(item.last_price) }}</td>
                  <td
                    :class="{
                      up: (item.change_pct || 0) > 0,
                      down: (item.change_pct || 0) < 0,
                    }"
                  >
                    {{ formatNum2(item.change_pct) }}
                  </td>
                  <td>{{ formatNum2(item.turnover_rate) }}</td>
                  <td>{{ formatNum2(item.volume_ratio) }}</td>
                  <td>{{ formatAmountYi(item.amount) }}</td>
                  <td>
                    <button type="button" class="link" @click.stop="onRemove(item)">删</button>
                  </td>
                </tr>
                <tr v-if="!displayedItems.length">
                  <td colspan="9" class="empty">
                    {{ items.length === 0 ? '自选为空，上方输入代码添加' : '无匹配结果' }}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>

        <section class="right">
          <div v-if="selected" class="chart-head">
            <strong>{{ selected.name || selected.vt_symbol }}</strong>
            <span v-if="selected.industry?.trim()" class="muted">{{ selected.industry }}</span>
            <span class="mono muted">{{ selected.vt_symbol }}</span>
            <span
              :class="{
                up: (selected.change_pct || 0) > 0,
                down: (selected.change_pct || 0) < 0,
              }"
            >
              {{ selected.last_price != null ? selected.last_price.toFixed(2) : '—' }}
              ·
              {{ selected.change_pct != null ? selected.change_pct.toFixed(2) + '%' : '—' }}
            </span>
            <div class="limits">
              <button
                v-for="n in [60, 90, 120]"
                :key="n"
                type="button"
                class="chip"
                :class="{ on: barLimit === n }"
                @click="barLimit = n"
              >
                {{ n }}日
              </button>
            </div>
          </div>
          <p v-else class="muted">选择左侧标的查看日 K</p>
          <p v-if="barsError" class="err">{{ barsError }}</p>

          <div class="chart" v-if="bars.length">
            <CandleChart :bars="bars" />
            <div class="bar-meta muted">
              {{ bars[0].datetime.slice(0, 10) }} → {{ bars[bars.length - 1].datetime.slice(0, 10) }}
              · {{ bars.length }} 根日 K
            </div>
          </div>

          <div class="table-wrap mini" v-if="bars.length">
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
                  <td class="mono">{{ b.datetime.slice(0, 10) }}</td>
                  <td>{{ b.open.toFixed(2) }}</td>
                  <td>{{ b.high.toFixed(2) }}</td>
                  <td>{{ b.low.toFixed(2) }}</td>
                  <td>{{ b.close.toFixed(2) }}</td>
                  <td>{{ Math.round(b.volume).toLocaleString() }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>
      </div>

      <section class="strategy">
        <div class="pos-form risk-card">
          <h3>仓位与风控</h3>
          <div class="risk-summary muted" v-if="riskSummary">
            <span>实际仓位 {{ formatPctRatio(riskSummary.actual_position_pct) }}</span>
            <button
              v-if="riskSummary.off_plan_count > 0"
              type="button"
              class="link"
              @click="toggleOffPlanChips"
            >
              计划外 {{ riskSummary.off_plan_count }}
            </button>
            <span v-else>计划外 {{ riskSummary.off_plan_count }}</span>
            <span>计划日 {{ riskSummary.active_plan_date || '—' }}</span>
          </div>
          <div v-if="showOffPlanChips && riskSummary?.off_plan_symbols?.length" class="chips">
            <span v-for="vt in riskSummary.off_plan_symbols" :key="vt" class="chip-tag">
              <button type="button" class="chip-link mono" @click="selectVt(vt)">{{ vt }}</button>
            </span>
          </div>
          <div class="pos-grid risk-grid">
            <label>
              总资金
              <input
                v-model="riskForm.total_capital"
                type="number"
                step="1000"
                min="0"
                placeholder="可选"
                :disabled="!prefsReady || riskSaving"
              />
            </label>
            <label>
              止损%
              <input
                v-model="riskForm.stop_loss_pct"
                type="number"
                step="0.1"
                min="0.1"
                max="50"
                :disabled="!prefsReady || riskSaving"
              />
            </label>
            <label>
              浮亏警戒
              <input
                v-model="riskForm.caution_float_pct"
                type="number"
                step="0.5"
                max="-0.1"
                :disabled="!prefsReady || riskSaving"
              />
            </label>
          </div>
          <div class="row pos-actions">
            <button
              type="button"
              class="primary"
              :disabled="!prefsReady || riskSaving"
              @click="saveTradingRisk"
            >
              {{ riskSaving ? '保存中…' : '保存风控' }}
            </button>
          </div>
          <p v-if="!prefsReady" class="muted">加载风控偏好…</p>
          <p v-else-if="riskError" class="err">{{ riskError }}</p>
          <p v-else-if="riskMsg" class="muted">{{ riskMsg }}</p>
          <p class="muted tip">止损按百分数填写（如 5 = 5%）；浮亏警戒为负数（如 -5）。写入用户风控偏好。</p>
        </div>

        <div class="pos-form plan-card">
          <h3>
            当日计划
            <span class="muted" v-if="riskSummary?.active_plan_date">
              {{ riskSummary.active_plan_date }}
            </span>
          </h3>
          <p v-if="!planSymbols.length" class="muted">当日无 active 计划</p>
          <ul v-else class="plan-list">
            <li
              v-for="row in planSymbols"
              :key="row.vt_symbol"
              :class="{ on: selected?.vt_symbol === row.vt_symbol }"
              @click="selectVt(row.vt_symbol)"
            >
              <button type="button" class="chip-link mono" @click.stop="selectVt(row.vt_symbol)">
                {{ row.vt_symbol }}
              </button>
              <span class="plan-name">{{ row.name || '—' }}</span>
              <span class="plan-tag">{{ planSymbolLabel(row) }}</span>
            </li>
          </ul>
        </div>

        <div class="pos-form notify-card">
          <div class="notify-head">
            <h3>通知历史</h3>
            <div class="notify-actions">
              <button
                v-if="notifyOpen"
                type="button"
                class="ghost"
                :disabled="notifyLoading"
                @click="loadNotifyLog"
              >
                {{ notifyLoading ? '加载中…' : '刷新' }}
              </button>
              <button type="button" class="ghost" @click="toggleNotifyOpen">
                {{ notifyOpen ? '收起' : '展开' }}
              </button>
            </div>
          </div>
          <div v-if="notifyOpen" class="notify-body">
            <p v-if="notifyLoading && !notifyLoaded" class="muted">加载通知历史…</p>
            <p v-else-if="notifyError" class="err">{{ notifyError }}</p>
            <template v-else>
              <div class="table-wrap notify-table" v-if="notifyItems.length">
                <table>
                  <thead>
                    <tr>
                      <th>时间</th>
                      <th>事件</th>
                      <th>渠道</th>
                      <th>状态</th>
                      <th>错误</th>
                    </tr>
                  </thead>
                  <tbody>
                    <template v-for="row in notifyItems" :key="row.id">
                      <tr
                        :class="{ on: notifyExpandedId === row.id }"
                        @click="toggleNotifyRow(row.id)"
                      >
                        <td class="mono">{{ row.created_at || '—' }}</td>
                        <td>{{ row.event_type || '—' }}</td>
                        <td>{{ row.channel || '—' }}</td>
                        <td :class="notifyStatusClass(row.status)">{{ row.status || '—' }}</td>
                        <td class="clip">{{ row.error || '—' }}</td>
                      </tr>
                      <tr v-if="notifyExpandedId === row.id" class="notify-payload-row">
                        <td colspan="5">
                          <pre class="notify-payload">{{ prettyPayload(row.payload) }}</pre>
                        </td>
                      </tr>
                    </template>
                  </tbody>
                </table>
              </div>
              <p v-else class="muted tip">暂无通知投递记录</p>
            </template>
          </div>
        </div>

        <div class="strategy-head">
          <h2>策略看盘</h2>
          <span class="muted" v-if="board">
            {{ board.config_key }} · {{ board.source }} · as_of {{ board.as_of || '—' }}
          </span>
          <button type="button" class="ghost" @click="refreshBoard()">刷新看板</button>
        </div>
        <p v-if="boardError" class="err">{{ boardError }}</p>
        <p v-else-if="board?.note" class="muted">{{ board.note }}</p>

        <div class="strategy-grid" v-if="board">
          <div class="panel">
            <h3>
              信号区
              <span class="muted">{{ board.signals.length }}</span>
              <span class="muted"> · 名单 {{ panelSymbols.length }}/{{ panelMax }}</span>
            </h3>
            <div class="pos-form signal-form">
              <div class="row">
                <input
                  v-model="signalAdd"
                  placeholder="加入信号名单：600519.SSE"
                  @keyup.enter="addToSignalPanel()"
                />
                <button type="button" class="ghost" @click="addToSignalPanel(selected?.vt_symbol)">
                  用选中
                </button>
                <button type="button" class="primary" @click="addToSignalPanel()">加入</button>
              </div>
              <div class="chips" v-if="panelSymbols.length">
                <span v-for="vt in panelSymbols" :key="vt" class="chip-tag">
                  <button type="button" class="chip-link" @click="selectVt(vt)">{{ vt }}</button>
                  <button type="button" class="link" @click="removeFromSignalPanel(vt)">×</button>
                </span>
              </div>
              <p v-else class="muted tip">名单为空时回退「自选 ∩ 策略 cache」；上限 {{ panelMax }} 只（存 PG）。</p>
              <p v-if="signalError" class="err">{{ signalError }}</p>
              <p v-else-if="signalMsg" class="muted">{{ signalMsg }}</p>
            </div>
            <div class="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>代码</th>
                    <th>名称</th>
                    <th>现价</th>
                    <th>信号</th>
                    <th>强度</th>
                    <th>摘要</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  <tr
                    v-for="row in board.signals"
                    :key="row.vt_symbol"
                    :class="{ on: selected?.vt_symbol === row.vt_symbol }"
                    @click="selectVt(row.vt_symbol)"
                  >
                    <td class="mono">{{ row.vt_symbol }}</td>
                    <td>{{ row.name || '—' }}</td>
                    <td>{{ row.last_price != null ? row.last_price.toFixed(2) : '—' }}</td>
                    <td :class="signalClass(row.signal)">{{ row.signal_label }}</td>
                    <td>{{ row.strength != null ? row.strength.toFixed(0) : '—' }}</td>
                    <td class="clip">{{ row.reason_summary || '—' }}</td>
                    <td>
                      <button
                        v-if="panelSymbols.includes(row.vt_symbol)"
                        type="button"
                        class="link"
                        @click.stop="removeFromSignalPanel(row.vt_symbol)"
                      >
                        移出
                      </button>
                      <button
                        v-else
                        type="button"
                        class="link"
                        @click.stop="addToSignalPanel(row.vt_symbol)"
                      >
                        入名单
                      </button>
                    </td>
                  </tr>
                  <tr v-if="!board.signals.length">
                    <td colspan="7" class="empty">无信号（可先编辑名单，或确认策略 cache 已写入）</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          <div class="panel">
            <h3>持仓区 <span class="muted">{{ board.positions.length }}</span></h3>
            <div class="pos-form">
              <div class="pos-grid">
                <label>
                  代码
                  <input v-model="form.symbol" placeholder="600519.SSE" />
                </label>
                <label>
                  成本
                  <input v-model="form.cost_price" type="number" step="0.01" min="0" />
                </label>
                <label>
                  数量
                  <input v-model="form.volume" type="number" step="100" min="100" />
                </label>
                <label>
                  买入日
                  <input v-model="form.buy_date" type="date" />
                </label>
              </div>
              <label>
                备注
                <input v-model="form.notes" placeholder="可选" />
              </label>
              <div class="row pos-actions">
                <button type="button" class="ghost" @click="useSelectedForPos">用当前选中</button>
                <button type="button" class="ghost" @click="resetPosForm">清空</button>
                <button type="button" class="primary" @click="savePosition">
                  {{ editingVt ? '更新持仓' : '录入持仓' }}
                </button>
              </div>
              <p v-if="posError" class="err">{{ posError }}</p>
              <p v-else-if="posMsg" class="muted">{{ posMsg }}</p>
              <p class="muted tip">须先加入自选；数量 100 股整手；写入持仓记账表。</p>
            </div>
            <div class="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>代码</th>
                    <th>成本</th>
                    <th>数量</th>
                    <th>现价</th>
                    <th>市值</th>
                    <th>浮盈%</th>
                    <th>T+1</th>
                    <th>退出</th>
                    <th>风险</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  <tr
                    v-for="row in board.positions"
                    :key="row.vt_symbol + row.buy_date"
                    :class="{
                      on: selected?.vt_symbol === row.vt_symbol,
                      'off-plan': row.off_plan,
                    }"
                    @click="selectVt(row.vt_symbol)"
                  >
                    <td class="mono">{{ row.vt_symbol }}</td>
                    <td>{{ row.cost_price.toFixed(2) }}</td>
                    <td>{{ row.volume }}</td>
                    <td>{{ row.last_price != null ? row.last_price.toFixed(2) : '—' }}</td>
                    <td>{{ formatMarketValue(row.market_value) }}</td>
                    <td
                      :class="{
                        up: (row.unrealized_pnl_pct || 0) > 0,
                        down: (row.unrealized_pnl_pct || 0) < 0,
                      }"
                    >
                      {{ row.unrealized_pnl_pct != null ? row.unrealized_pnl_pct.toFixed(2) : '—' }}
                    </td>
                    <td>{{ row.t1_locked ? '锁定' : '可卖' }}</td>
                    <td :class="signalClass(row.exit_signal)">{{ row.exit_signal_label }}</td>
                    <td :class="{ warn: row.off_plan || row.risk_tags?.includes('计划外') }">
                      {{ row.risk_tags?.length ? row.risk_tags.join(' · ') : '—' }}
                    </td>
                    <td>
                      <button type="button" class="link" @click.stop="editBoardPosition(row)">改</button>
                      <button type="button" class="link" @click.stop="removePosition(row.vt_symbol)">删</button>
                    </td>
                  </tr>
                  <tr v-if="!board.positions.length">
                    <td colspan="10" class="empty">无持仓，上方可录入（投研记账，非实盘）</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </section>
    </div>
  </AppShell>
</template>

<style scoped>
.page {
  display: grid;
  grid-template-rows: 1fr auto;
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
}
.strategy {
  border-top: 1px solid var(--line);
  padding: 14px 24px 18px;
  display: grid;
  gap: 12px;
  background: var(--surface);
  box-shadow: 0 -1px 0 var(--line-soft);
}
.strategy-head {
  display: flex;
  gap: 12px;
  align-items: center;
  flex-wrap: wrap;
}
.strategy-head h2 {
  margin: 0;
  font-size: 1rem;
}
.strategy-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}
.panel h3 {
  margin: 0 0 8px;
  font-size: 0.9rem;
  font-weight: 600;
}
.pos-form {
  display: grid;
  gap: 8px;
  margin-bottom: 10px;
  padding: 10px;
  border: 1px solid var(--border);
  border-radius: 0.75rem;
  background: var(--surface-muted);
}
.risk-card {
  margin-bottom: 0;
}
.risk-card h3 {
  margin: 0;
  font-size: 0.9rem;
  font-weight: 600;
}
.risk-summary {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  font-size: 0.8rem;
}
.risk-grid {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}
.plan-card {
  margin-top: 10px;
  margin-bottom: 0;
}
.plan-card h3 {
  margin: 0;
  font-size: 0.9rem;
  font-weight: 600;
  display: flex;
  gap: 8px;
  align-items: baseline;
}
.plan-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 4px;
}
.plan-list li {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 6px;
  border-radius: 6px;
  cursor: pointer;
}
.plan-list li:hover,
.plan-list li.on {
  background: var(--brand-light);
}
.plan-name {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 0.85rem;
}
.plan-tag {
  font-size: 0.75rem;
  color: var(--muted);
  flex-shrink: 0;
}
.notify-card {
  margin-top: 10px;
  margin-bottom: 0;
}
.notify-card h3 {
  margin: 0;
  font-size: 0.9rem;
  font-weight: 600;
}
.notify-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  flex-wrap: wrap;
}
.notify-actions {
  display: flex;
  gap: 8px;
}
.notify-body {
  display: grid;
  gap: 8px;
}
.notify-table {
  max-height: 240px;
}
.notify-payload-row {
  cursor: default;
}
.notify-payload-row td {
  white-space: normal;
  background: var(--surface-muted);
  padding: 8px 10px;
}
.notify-payload {
  margin: 0;
  max-height: 180px;
  overflow: auto;
  font-family: var(--mono);
  font-size: 0.75rem;
  color: var(--muted);
  white-space: pre-wrap;
  word-break: break-word;
}
.pos-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 8px;
}
.pos-actions {
  grid-template-columns: auto auto 1fr;
  justify-items: start;
}
.pos-actions .primary {
  justify-self: end;
}
.tip {
  margin: 0;
  font-size: 0.75rem;
}
.chips {
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
  padding: 2px 6px;
  font-size: 0.8rem;
  background: var(--bg);
}
.chip-link {
  background: none;
  border: none;
  color: var(--text);
  font-family: var(--mono);
  padding: 0;
  cursor: pointer;
}
.signal-form .row {
  grid-template-columns: 1fr auto auto;
}
.clip {
  max-width: 220px;
  overflow: hidden;
  text-overflow: ellipsis;
}
.row {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 8px;
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
  margin-left: auto;
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
.muted {
  color: var(--muted);
  font-size: 0.85rem;
}
.table-wrap {
  border: 1px solid var(--line);
  border-radius: 0.75rem;
  overflow: auto;
  background: var(--surface);
  box-shadow: var(--shadow-card);
  max-height: 320px;
}
.strategy .table-wrap {
  max-height: 220px;
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
tbody tr.on {
  background: var(--brand-light);
}
tbody tr.off-plan {
  background: #fee2e2;
}
tbody tr.off-plan.on {
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
  gap: 12px;
  align-items: center;
  flex-wrap: wrap;
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
@media (max-width: 900px) {
  .workspace,
  .strategy-grid,
  .pos-grid,
  .risk-grid {
    grid-template-columns: 1fr;
  }
  .left {
    border-right: none;
    border-bottom: 1px solid var(--border);
  }
}
</style>

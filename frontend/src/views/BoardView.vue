<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AppShell from '../components/AppShell.vue'
import { confirmDialog } from '../lib/dialog'
import {
  watchlistApi,
  type PositionItem,
  type StrategyBoard,
} from '../api/watchlist'
import { backtestApi } from '../api/backtest'
import { buildAlignedBacktestQuery, buildEnqueueRunBody } from '../lib/boardBacktestParams'

const router = useRouter()
const route = useRoute()

const board = ref<StrategyBoard | null>(null)
const boardError = ref('')
const positions = ref<PositionItem[]>([])
const enqueueing = ref(false)

const SIGNAL_MODE_KEY = 'zak2:watchlist:signal_mode'
type SignalMode = 'heuristic_v2' | 'double_ma' | 'trend_ma'
const VALID_SIGNAL_MODES: SignalMode[] = ['heuristic_v2', 'double_ma', 'trend_ma']

function loadSignalMode(): SignalMode {
  try {
    const v = localStorage.getItem(SIGNAL_MODE_KEY)
    if (v && (VALID_SIGNAL_MODES as string[]).includes(v)) return v as SignalMode
  } catch {
    /* ignore */
  }
  return 'heuristic_v2'
}

function saveSignalMode(mode: SignalMode) {
  localStorage.setItem(SIGNAL_MODE_KEY, mode)
}

const signalMode = ref<SignalMode>(loadSignalMode())

const activeSignalVt = ref('')
const signalAdd = ref('')
const signalError = ref('')
const signalMsg = ref('')

const posError = ref('')
const posMsg = ref('')
const editingVt = ref('')
const form = ref({
  symbol: '',
  cost_price: '',
  volume: '100',
  buy_date: new Date().toISOString().slice(0, 10),
  notes: '',
})

const riskForm = ref({
  total_capital: '',
  stop_loss_pct: '',
  caution_float_pct: '',
})
const prefsReady = ref(false)
const riskError = ref('')
const riskMsg = ref('')
const riskSaving = ref(false)

let boardTimer: number | undefined

const panelSymbols = computed(() => board.value?.panel_symbols || [])
const panelMax = 10
const riskSummary = computed(() => board.value?.risk_summary ?? null)

function formatPctRatio(v: number | null | undefined): string {
  if (v == null || Number.isNaN(v)) return '—'
  return `${(v * 100).toFixed(1)}%`
}

function formatMarketValue(v: number | null | undefined): string {
  if (v == null || Number.isNaN(v)) return '—'
  return v.toLocaleString()
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

function signalClass(sig: string) {
  if (sig === 'buy') return 'up'
  if (sig === 'sell') return 'down'
  return ''
}

async function refreshBoard(quiet = false) {
  if (!quiet) boardError.value = ''
  const loadPrefs = !quiet || !prefsReady.value
  try {
    const [b, pos, prefs] = await Promise.all([
      watchlistApi.strategyBoard({ signalMode: signalMode.value }),
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

function setSignalMode(mode: SignalMode) {
  if (signalMode.value === mode) return
  signalMode.value = mode
  saveSignalMode(mode)
  void refreshBoard()
}

function selectVt(vt: string) {
  if (!vt) return
  void router.push({ path: '/watchlist', query: { symbol: vt } })
}

function pickSignal(vt: string) {
  activeSignalVt.value = activeSignalVt.value === vt ? '' : vt
}

function resolveBoardVtSymbol(): string {
  return activeSignalVt.value || board.value?.signals[0]?.vt_symbol || ''
}

function openAlignedBacktest() {
  const vt = resolveBoardVtSymbol()
  if (!vt) {
    boardError.value = '无可用标的，请在信号区选中或等待信号'
    return
  }
  void router.push({
    path: '/backtest',
    query: buildAlignedBacktestQuery(signalMode.value, vt, board.value?.config_key || ''),
  })
}

async function enqueueAlignedBacktest() {
  const vt = resolveBoardVtSymbol()
  if (!vt) {
    boardError.value = '无可用标的，请在信号区选中或等待信号'
    return
  }
  const body = buildEnqueueRunBody(signalMode.value, vt, board.value?.config_key || '')
  const ok = await confirmDialog({
    title: '入队回测',
    message: `对 ${vt} 入队 ${body.strategy} ${body.fast_window}/${body.slow_window}，区间 ${body.start_date}～${body.end_date}，资金 ${body.capital}？`,
  })
  if (!ok) return
  enqueueing.value = true
  boardError.value = ''
  try {
    const { job_id } = await backtestApi.start(body)
    void router.push({ path: '/backtest', query: { job_id } })
  } catch (e) {
    boardError.value = e instanceof Error ? e.message : '入队回测失败'
  } finally {
    enqueueing.value = false
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

function resetPosForm() {
  editingVt.value = ''
  form.value = {
    symbol: '',
    cost_price: '',
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

function editBoardPosition(row: {
  vt_symbol: string
  cost_price: number
  volume: number
  buy_date: string
}) {
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
    sort_order: 0,
    created_at: '',
    updated_at: '',
  })
}

async function savePosition() {
  posError.value = ''
  posMsg.value = ''
  const symbol = form.value.symbol.trim()
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

async function addToSignalPanel(raw?: string) {
  signalError.value = ''
  signalMsg.value = ''
  const symbol = (raw || signalAdd.value || '').trim()
  if (!symbol) {
    signalError.value = '请填写代码或先在信号区选中'
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

function tickBoard() {
  if (document.hidden) return
  void refreshBoard(true)
}

onMounted(async () => {
  const sm = typeof route.query.signal_mode === 'string' ? route.query.signal_mode : ''
  if ((VALID_SIGNAL_MODES as string[]).includes(sm)) {
    const mode = sm as SignalMode
    signalMode.value = mode
    saveSignalMode(mode)
  }
  await refreshBoard()
  boardTimer = window.setInterval(tickBoard, 45000)
})

onUnmounted(() => {
  if (boardTimer) window.clearInterval(boardTimer)
})
</script>

<template>
  <AppShell title="看板" subtitle="策略看盘 · 持仓 · 风控" active="board">
    <div class="page">
      <p v-if="boardError" class="err">{{ boardError }}</p>

      <div class="summary-grid">
        <section class="card risk-card">
          <h3>仓位与风控</h3>
          <div v-if="riskSummary" class="risk-summary muted">
            <span>实际仓位 {{ formatPctRatio(riskSummary.actual_position_pct) }}</span>
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
          <div class="actions">
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
          <p class="muted tip">止损按百分数（如 5 = 5%）；浮亏警戒为负数（如 -5）。</p>
        </section>
      </div>

      <div class="board-head">
        <h2>策略看盘</h2>
        <span v-if="board" class="muted">
          {{ board.config_key }} · {{ board.signal_mode || signalMode }} · {{ board.source }} ·
          as_of {{ board.as_of || '—' }}
        </span>
        <div class="mode-tabs">
          <button
            type="button"
            class="ghost"
            :class="{ on: signalMode === 'heuristic_v2' }"
            @click="setSignalMode('heuristic_v2')"
          >
            启发式确认
          </button>
          <button
            type="button"
            class="ghost"
            :class="{ on: signalMode === 'double_ma' }"
            @click="setSignalMode('double_ma')"
          >
            回测双均线
          </button>
          <button
            type="button"
            class="ghost"
            :class="{ on: signalMode === 'trend_ma' }"
            @click="setSignalMode('trend_ma')"
          >
            趋势均线
          </button>
        </div>
        <button type="button" class="ghost" @click="openAlignedBacktest()">同参回测</button>
        <button
          type="button"
          class="ghost"
          :disabled="enqueueing"
          @click="enqueueAlignedBacktest()"
        >
          {{ enqueueing ? '入队中…' : '入队回测' }}
        </button>
        <button type="button" class="ghost" @click="refreshBoard()">刷新看板</button>
      </div>
      <p v-if="board?.note" class="muted">{{ board.note }}</p>

      <div v-if="board" class="board-grid">
        <section class="card">
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
              <button type="button" class="ghost" @click="addToSignalPanel(activeSignalVt)">
                用选中
              </button>
              <button type="button" class="primary" @click="addToSignalPanel()">加入</button>
            </div>
            <div v-if="panelSymbols.length" class="chips">
              <span v-for="vt in panelSymbols" :key="vt" class="chip-tag">
                <button type="button" class="chip-link" @click="selectVt(vt)">{{ vt }}</button>
                <button type="button" class="link" @click="removeFromSignalPanel(vt)">×</button>
              </span>
            </div>
            <p v-else class="muted tip">名单为空时回退「自选 ∩ 策略 cache」；上限 {{ panelMax }} 只。</p>
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
                  :class="{ on: activeSignalVt === row.vt_symbol }"
                  @click="pickSignal(row.vt_symbol)"
                >
                  <td class="mono">{{ row.vt_symbol }}</td>
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
                  <td colspan="7" class="empty">
                    无信号（可先编辑名单，或确认策略 cache 已写入）
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>

        <section class="card">
          <h3>
            持仓区 <span class="muted">{{ board.positions.length }}</span>
          </h3>
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
            <div class="actions">
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
                >
                  <td class="mono">
                    <button type="button" class="chip-link" @click="selectVt(row.vt_symbol)">
                      {{ row.vt_symbol }}
                    </button>
                  </td>
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
                  <td>{{ row.risk_tags?.length ? row.risk_tags.join(' · ') : '—' }}</td>
                  <td>
                    <button type="button" class="link" @click.stop="editBoardPosition(row)">
                      改
                    </button>
                    <button type="button" class="link" @click.stop="removePosition(row.vt_symbol)">
                      删
                    </button>
                  </td>
                </tr>
                <tr v-if="!board.positions.length">
                  <td colspan="10" class="empty">无持仓，上方可录入（投研记账，非实盘）</td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>
      </div>
    </div>
  </AppShell>
</template>

<style scoped>
.page {
  display: grid;
  gap: 16px;
  padding: 16px 24px 24px;
}
.card {
  border: 1px solid var(--line);
  border-radius: 0.75rem;
  background: var(--surface);
  box-shadow: var(--shadow-card);
  padding: 14px 16px;
}
.card h3 {
  margin: 0 0 10px;
  font-size: 0.9rem;
  font-weight: 600;
}
.summary-grid {
  display: grid;
  gap: 12px;
  align-items: start;
}
.risk-summary {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  font-size: 0.8rem;
  margin-bottom: 8px;
}
.risk-grid {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}
.pos-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 8px;
}
.actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 8px;
}
.board-head {
  display: flex;
  gap: 12px;
  align-items: center;
  flex-wrap: wrap;
}
.board-head h2 {
  margin: 0;
  font-size: 1rem;
}
.mode-tabs {
  display: inline-flex;
  gap: 4px;
}
.board-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
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
.signal-form .row {
  grid-template-columns: 1fr auto auto;
}
.row {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 8px;
}
label {
  display: grid;
  gap: 6px;
  font-size: 0.8rem;
  color: var(--muted);
}
input {
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: 0.5rem;
  color: var(--text);
  padding: 8px 10px;
}
input:focus {
  border-color: var(--brand);
  box-shadow: 0 0 0 3px rgba(230, 100, 50, 0.15);
  outline: none;
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
.chip-link:hover {
  color: var(--brand);
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
.primary {
  background: var(--accent);
  color: var(--brand-foreground);
  border: none;
  border-radius: 0.5rem;
  padding: 8px 12px;
  font-weight: 600;
}
.primary:hover:not(:disabled) {
  background: var(--brand-dark);
}
.primary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.ghost {
  background: transparent;
  border: 1px solid var(--border);
  color: var(--text);
  border-radius: 0.5rem;
  padding: 8px 12px;
}
.ghost:hover:not(:disabled) {
  background: var(--brand-light);
  color: var(--brand);
  border-color: var(--brand-soft);
}
.ghost.on {
  background: var(--brand-light);
  color: var(--brand);
  border-color: var(--brand-soft);
  font-weight: 500;
}
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
tbody tr {
  cursor: pointer;
}
tbody tr:hover td {
  background: var(--surface-muted);
}
tbody tr.on td {
  background: var(--brand-light);
}
.clip {
  max-width: 220px;
  overflow: hidden;
  text-overflow: ellipsis;
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
.muted {
  color: var(--muted);
  font-size: 0.85rem;
}
.tip {
  margin: 0;
  font-size: 0.75rem;
}
.err {
  margin: 0;
  color: var(--danger);
  font-size: 0.85rem;
}
@media (max-width: 900px) {
  .summary-grid,
  .board-grid,
  .pos-grid,
  .risk-grid {
    grid-template-columns: 1fr;
  }
}
</style>

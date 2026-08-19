<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import AppShell from '../components/AppShell.vue'
import StockAnalysisModal from '../components/StockAnalysisModal.vue'
import { backtestApi, type StrategyInfo } from '../api/backtest'
import { watchlistApi, type StrategyBoard } from '../api/watchlist'
import { POLL_SLOW_MS, useQuoteNotify } from '../composables/useQuoteNotify'
import { useStockAnalysis } from '../composables/useStockAnalysis'
import {
  buildAlignedBacktestQuery,
  type BoardSignalMode,
} from '../lib/boardBacktestParams'

const analysis = useStockAnalysis()

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
                <th>操作</th>
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
                <td>
                  <button
                    type="button"
                    class="link"
                    @click.stop="analysis.open(row.vt_symbol, row.name)"
                  >
                    析
                  </button>
                </td>
              </tr>
              <tr v-if="!activeBoard.signals.length">
                <td colspan="7" class="empty">
                  无信号（可去 Ops 跑 warm_watchlist_strategy_cache 预热）
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <p v-else class="s muted">加载中…</p>
      </section>
    </div>
  </AppShell>
  <StockAnalysisModal />
</template>

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

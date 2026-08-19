<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import AppShell from '../components/AppShell.vue'
import { backtestApi, type StrategyInfo } from '../api/backtest'
import { watchlistApi, type StrategyBoard } from '../api/watchlist'
import { buildAlignedBacktestQuery, type BoardSignalMode } from '../lib/boardBacktestParams'

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

const boardList = computed(() =>
  SIGNAL_MODES.map((m) => ({
    ...m,
    board: boards.value[m.id] || null,
    error: boardErrors.value[m.id] || '',
  })),
)

async function load() {
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

onMounted(() => {
  void load()
})
</script>

<template>
  <AppShell title="策略" subtitle="策略信号总览 · 回测策略清单" active="strategies">
    <div class="page">
      <p class="muted hint">
        三轨信号缓存（启发式 / 双均线 / 趋势均线）；无数据时可去 Ops 跑
        <code>warm_watchlist_strategy_cache</code> 预热。
        <RouterLink to="/ops" class="draft-link">去 Ops</RouterLink>
      </p>

      <section class="cards">
        <div v-for="m in boardList" :key="m.id" class="card">
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
    </div>
  </AppShell>
</template>

<style scoped>
.page {
  display: grid;
  gap: 14px;
}
.hint {
  margin: 0;
  font-size: 0.8rem;
  max-width: 56ch;
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
.tiny-btn {
  padding: 4px 8px;
  font-size: 0.8rem;
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

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import AppShell from '../../../components/AppShell.vue'
import BarsChartModal from '../../../components/BarsChartModal.vue'
import FundamentalsModal from '../../../components/FundamentalsModal.vue'
import StockAnalysisModal from '../../analysis/components/StockAnalysisModal.vue'
import { marketApi, type MarketOverview, type RankRow } from '../../../api/market'
import { watchlistApi } from '../../../api/watchlist'
import { usePolling } from '../../../composables/usePolling'
import { POLL_FAST_MS, POLL_SLOW_MS, useQuoteNotify } from '../../../composables/useQuoteNotify'
import { useStockAnalysis } from '../../analysis/composables/useStockAnalysis'
import MarketOverviewCards from '../components/MarketOverviewCards.vue'
import MarketRankBoard from '../components/MarketRankBoard.vue'
import MarketThresholdsPanel from '../components/MarketThresholdsPanel.vue'

const analysis = useStockAnalysis()

const overview = ref<MarketOverview | null>(null)
const field = ref('change_pct')
// 0 表示全部（后端全量上限以内）
const rankLimit = ref(50)
const ranks = ref<RankRow[]>([])
const error = ref('')
const loading = ref(false)
const autoRefresh = ref(true)
const chartVt = ref('')
const fundVt = ref('')
// 搜索关键词激活时强制全量拉取，由 MarketRankBoard 通过 search-active 同步
const searchActive = ref(false)

const chartName = computed(() => ranks.value.find((r) => r.vt_symbol === chartVt.value)?.name || '')
const fundName = computed(() => ranks.value.find((r) => r.vt_symbol === fundVt.value)?.name || '')

// 0 表示全部：请求一个覆盖全市场的上限（后端 le=20000）
const FULL_RANK_TOP = 20000
function rankTopN(): number {
  if (searchActive.value) return FULL_RANK_TOP
  return rankLimit.value === 0 ? FULL_RANK_TOP : rankLimit.value
}

const watchSet = ref<Set<string>>(new Set())
// 休市时数据静止，无需高频拉取；慢轮询兜底以便开市后自动切回
const CLOSED_POLL_MS = 5 * 60_000
const thresholdsPanel = ref<InstanceType<typeof MarketThresholdsPanel> | null>(null)

const { connected } = useQuoteNotify({
  onQuotesUpdated: () => {
    if (!autoRefresh.value || document.hidden) return
    void load(true)
  },
})

function pollIntervalMs(): number {
  if (overview.value && !overview.value.is_trading) return CLOSED_POLL_MS
  return connected.value ? POLL_SLOW_MS : POLL_FAST_MS
}

function tick() {
  if (!autoRefresh.value || document.hidden) return
  void load(true)
}

const { restart: restartPoll } = usePolling(tick, pollIntervalMs, [
  connected,
  () => overview.value?.is_trading,
])

const subtitle = computed(() => {
  const o = overview.value
  if (!o) return ''
  const cycle = o.emotion_cycle
  if (cycle?.stage_label) {
    const gate = cycle.allow_new_positions ? '可新开' : '不宜新开'
    return `行情 ${o.quote_count} · ${cycle.stage_label} · ${gate}`
  }
  return `行情 ${o.quote_count}`
})

const refreshLabel = computed(() => {
  if (!autoRefresh.value) return '已暂停自动刷新'
  if (overview.value && !overview.value.is_trading) return '休市 · 5 分钟刷新'
  return connected.value ? 'WS + 慢轮询' : '15 秒刷新'
})

async function load(quiet = false) {
  if (!quiet) loading.value = true
  error.value = ''
  try {
    overview.value = await marketApi.overview()
    try {
      ranks.value = await marketApi.ranks(field.value, rankTopN())
    } catch (e) {
      ranks.value = []
      if (overview.value.quote_count === 0) {
        error.value = 'Redis 行情为空（排行不可用）；情绪梯队仍可读'
      } else {
        error.value = e instanceof Error ? e.message : '排行加载失败'
      }
    }
  } catch (e) {
    error.value = e instanceof Error ? e.message : '加载失败'
  } finally {
    loading.value = false
  }
}

async function onField() {
  error.value = ''
  chartVt.value = ''
  try {
    ranks.value = await marketApi.ranks(field.value, rankTopN())
  } catch (e) {
    ranks.value = []
    error.value = e instanceof Error ? e.message : '排行加载失败'
  }
}

async function loadWatchSet() {
  try {
    const items = await watchlistApi.list()
    watchSet.value = new Set(items.map((i) => i.vt_symbol))
  } catch {
    // 静默失败，加自选操作仍可用
  }
}

async function toggleWatch(r: RankRow) {
  const vt = r.vt_symbol
  if (watchSet.value.has(vt)) {
    await watchlistApi.remove(vt)
    watchSet.value.delete(vt)
    return
  }
  await watchlistApi.add(r.symbol, r.name || '')
  watchSet.value.add(vt)
}

function onSearchActive(active: boolean) {
  searchActive.value = active
  void load(true)
}

watch(field, () => {
  void onField()
})

watch(rankLimit, () => {
  void load(true)
})

onMounted(() => {
  void load()
  void loadWatchSet()
  restartPoll()
})
</script>

<template>
  <AppShell title="市场" :subtitle="subtitle" active="market">
    <div class="page">
      <MarketOverviewCards
        v-if="overview"
        :overview="overview"
        @open-thresholds="thresholdsPanel?.openFromCard()"
      />
      <MarketThresholdsPanel
        v-if="overview?.emotion_cycle"
        ref="thresholdsPanel"
        @saved="() => load(true)"
      />

      <MarketRankBoard
        v-model:field="field"
        v-model:rank-limit="rankLimit"
        v-model:auto-refresh="autoRefresh"
        :ranks="ranks"
        :loading="loading"
        :error="error"
        :refresh-label="refreshLabel"
        :watch-set="watchSet"
        @refresh="load()"
        @search-active="onSearchActive"
        @toggle-watch="toggleWatch"
        @chart="(vt) => (chartVt = vt)"
        @fund="(vt) => (fundVt = vt)"
        @analyze="(vt, name) => analysis.open(vt, name)"
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
}
</style>

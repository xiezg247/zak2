<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'
import AppShell from '../../../components/AppShell.vue'
import StockAnalysisModal from '../../analysis/components/StockAnalysisModal.vue'
import { usePolling } from '../../../composables/usePolling'
import { POLL_FAST_MS, POLL_SLOW_MS, useQuoteNotify } from '../../../composables/useQuoteNotify'
import { useStockAnalysis } from '../../analysis/composables/useStockAnalysis'
import { useStrategyBoard } from '../../../composables/useStrategyBoard'
import WatchlistSignalsToolbar from '../components/WatchlistSignalsToolbar.vue'
import WatchlistSignalsPanel from '../components/WatchlistSignalsPanel.vue'

const analysis = useStockAnalysis()
const sb = reactive(useStrategyBoard())
const route = useRoute()
const autoRefresh = ref(true)

const { connected } = useQuoteNotify({
  onQuotesUpdated: () => {
    if (!autoRefresh.value || document.hidden) return
    void sb.refreshBoard(true)
  },
})

function tick() {
  if (!autoRefresh.value || document.hidden) return
  void sb.refreshBoard(true)
}

usePolling(
  tick,
  () => (connected.value ? POLL_SLOW_MS : POLL_FAST_MS),
  [connected],
)

const subtitle = computed(() => {
  const n = sb.board?.signals.length ?? 0
  const p = sb.panelSymbols.length
  return `${n} 个信号 · 名单 ${p}/${sb.panelMax}`
})

onMounted(async () => {
  await sb.loadStrategies()
  sb.applyQueryMode(route.query)
  await sb.refreshBoard()
})
</script>

<template>
  <AppShell title="策略信号" :subtitle="subtitle" active="watchlist-signals">
    <div class="page">
      <p v-if="sb.boardError" class="err">{{ sb.boardError }}</p>

      <WatchlistSignalsToolbar
        :signal-mode="sb.signalMode"
        :strategy-options="sb.strategyOptions"
        :risk-form="sb.riskForm"
        :prefs-ready="sb.prefsReady"
        :risk-saving="sb.riskSaving"
        :risk-error="sb.riskError"
        :risk-msg="sb.riskMsg"
        :enqueueing="sb.enqueueing"
        :auto-refresh="autoRefresh"
        @update:signal-mode="sb.signalMode = $event"
        @update:auto-refresh="autoRefresh = $event"
        @mode-change="sb.onSignalModeChange()"
        @save-risk="sb.saveTradingRisk()"
        @open-backtest="sb.openAlignedBacktest()"
        @enqueue-backtest="sb.enqueueAlignedBacktest()"
        @refresh="sb.refreshBoard()"
      />

      <p v-if="sb.board?.note" class="muted">{{ sb.board.note }}</p>

      <WatchlistSignalsPanel
        v-if="sb.board"
        :signals="sb.board.signals"
        :panel-symbols="sb.panelSymbols"
        :panel-max="sb.panelMax"
        :signal-add="sb.signalAdd"
        :active-signal-vt="sb.activeSignalVt"
        :signal-error="sb.signalError"
        :signal-msg="sb.signalMsg"
        @update:signal-add="sb.signalAdd = $event"
        @add="sb.addToSignalPanel($event)"
        @remove="sb.removeFromSignalPanel($event)"
        @select="sb.selectVt($event)"
        @pick="sb.pickSignal($event)"
        @analyze="(vt, name) => analysis.open(vt, name)"
      />
    </div>
  </AppShell>
  <StockAnalysisModal />
</template>

<style scoped>
.page {
  display: grid;
  gap: 14px;
  padding: 16px 24px 24px;
}
</style>

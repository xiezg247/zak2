<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'
import AppShell from '../../../components/AppShell.vue'
import StockAnalysisModal from '../../../components/StockAnalysisModal.vue'
import { usePolling } from '../../../composables/usePolling'
import { POLL_FAST_MS, POLL_SLOW_MS, useQuoteNotify } from '../../../composables/useQuoteNotify'
import { useStockAnalysis } from '../../../composables/useStockAnalysis'
import { useStrategyBoard } from '../../../composables/useStrategyBoard'
import { formatPrice } from '../../../lib/format'

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

      <div class="topbar">
        <div class="mode-select">
          <span>策略</span>
          <select v-model="sb.signalMode" @change="sb.onSignalModeChange()">
            <option v-for="m in sb.strategyOptions" :key="m.value" :value="m.value">
              {{ m.label }}
            </option>
          </select>
        </div>

        <div class="risk-form">
          <label>
            总资金
            <input
              v-model="sb.riskForm.total_capital"
              type="number"
              step="1000"
              min="0"
              placeholder="可选"
              :disabled="!sb.prefsReady || sb.riskSaving"
            />
          </label>
          <label>
            止损%
            <input
              v-model="sb.riskForm.stop_loss_pct"
              type="number"
              step="0.1"
              min="0.1"
              max="50"
              :disabled="!sb.prefsReady || sb.riskSaving"
            />
          </label>
          <label>
            浮亏警戒
            <input
              v-model="sb.riskForm.caution_float_pct"
              type="number"
              step="0.5"
              max="-0.1"
              :disabled="!sb.prefsReady || sb.riskSaving"
            />
          </label>
          <button
            type="button"
            class="primary"
            :disabled="!sb.prefsReady || sb.riskSaving"
            @click="sb.saveTradingRisk()"
          >
            {{ sb.riskSaving ? '保存中…' : '保存风控' }}
          </button>
        </div>

        <div class="actions">
          <button type="button" class="ghost" @click="sb.openAlignedBacktest()">同参回测</button>
          <button
            type="button"
            class="ghost"
            :disabled="sb.enqueueing"
            @click="sb.enqueueAlignedBacktest()"
          >
            {{ sb.enqueueing ? '入队中…' : '入队回测' }}
          </button>
          <button type="button" class="ghost" @click="sb.refreshBoard()">刷新看板</button>
          <label class="auto">
            <input v-model="autoRefresh" type="checkbox" />
            自动刷新
          </label>
        </div>
      </div>

      <div class="topbar-feedback">
        <p v-if="!sb.prefsReady" class="muted">加载风控偏好…</p>
        <p v-else-if="sb.riskError" class="err">{{ sb.riskError }}</p>
        <p v-else-if="sb.riskMsg" class="muted">{{ sb.riskMsg }}</p>
        <p class="muted tip">止损按百分数（如 5 = 5%）；浮亏警戒为负数（如 -5）。</p>
      </div>
      <p v-if="sb.board?.note" class="muted">{{ sb.board.note }}</p>

      <section v-if="sb.board" class="card">
        <h3>
          信号区
          <span class="muted">{{ sb.board.signals.length }}</span>
          <span class="muted"> · 名单 {{ sb.panelSymbols.length }}/{{ sb.panelMax }}</span>
        </h3>
        <div class="pos-form signal-form">
          <div class="row">
            <input
              v-model="sb.signalAdd"
              placeholder="加入信号名单：600519.SSE"
              @keyup.enter="sb.addToSignalPanel()"
            />
            <button type="button" class="ghost" @click="sb.addToSignalPanel(sb.activeSignalVt)">
              用选中
            </button>
            <button type="button" class="primary" @click="sb.addToSignalPanel()">加入</button>
          </div>
          <div v-if="sb.panelSymbols.length" class="chips">
            <span v-for="vt in sb.panelSymbols" :key="vt" class="chip-tag">
              <button type="button" class="chip-link" @click="sb.selectVt(vt)">{{ vt }}</button>
              <button type="button" class="link" @click="sb.removeFromSignalPanel(vt)">×</button>
            </span>
          </div>
          <p v-else class="muted tip">
            名单为空时回退「自选实时计算」；上限 {{ sb.panelMax }} 只。
          </p>
          <p v-if="sb.signalError" class="err">{{ sb.signalError }}</p>
          <p v-else-if="sb.signalMsg" class="muted">{{ sb.signalMsg }}</p>
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
                v-for="row in sb.board.signals"
                :key="row.vt_symbol"
                :class="{ on: sb.activeSignalVt === row.vt_symbol }"
                @click="sb.pickSignal(row.vt_symbol)"
              >
                <td class="mono">{{ row.vt_symbol }}</td>
                <td>{{ row.name || '—' }}</td>
                <td>{{ formatPrice(row.last_price) }}</td>
                <td :class="sb.signalClass(row.signal)">{{ row.signal_label }}</td>
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
                  <button
                    v-if="sb.panelSymbols.includes(row.vt_symbol)"
                    type="button"
                    class="link"
                    @click.stop="sb.removeFromSignalPanel(row.vt_symbol)"
                  >
                    移出
                  </button>
                  <button
                    v-else
                    type="button"
                    class="link"
                    @click.stop="sb.addToSignalPanel(row.vt_symbol)"
                  >
                    入名单
                  </button>
                </td>
              </tr>
              <tr v-if="!sb.board.signals.length">
                <td colspan="7" class="empty">无信号（可先编辑名单，或确认日 K 已补全）</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
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
.topbar {
  display: flex;
  align-items: flex-end;
  gap: 16px;
  flex-wrap: wrap;
  padding: 10px 12px;
  border: 1px solid var(--line);
  border-radius: 0.75rem;
  background: var(--surface);
  box-shadow: var(--shadow-card);
}
.mode-select {
  display: grid;
  gap: 4px;
  font-size: 0.78rem;
  color: var(--muted);
}
.mode-select select {
  min-width: 130px;
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: 0.5rem;
  color: var(--text);
  padding: 6px 8px;
}
.mode-select select:focus {
  border-color: var(--brand);
  box-shadow: 0 0 0 3px rgba(230, 100, 50, 0.15);
  outline: none;
}
.risk-form {
  display: flex;
  align-items: flex-end;
  gap: 10px;
  flex-wrap: wrap;
}
.risk-form label {
  display: grid;
  gap: 4px;
  font-size: 0.78rem;
  color: var(--muted);
}
.risk-form input {
  width: 110px;
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: 0.5rem;
  color: var(--text);
  padding: 6px 8px;
}
.risk-form input:focus {
  border-color: var(--brand);
  box-shadow: 0 0 0 3px rgba(230, 100, 50, 0.15);
  outline: none;
}
.topbar .actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  align-items: center;
  margin-left: auto;
}
.auto {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 0.8125rem;
  color: var(--ink-muted);
}
.topbar-feedback {
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
}
.topbar-feedback p {
  margin: 0;
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
  cursor: pointer;
}
.link:hover {
  color: var(--danger);
}
.clip {
  max-width: 220px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.tip {
  margin: 0;
  font-size: 0.75rem;
}
.table-wrap {
  overflow: auto;
}
table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.875rem;
}
th,
td {
  padding: 8px 10px;
  border-bottom: 1px solid var(--line-soft);
  text-align: left;
}
th {
  color: var(--ink-muted);
  font-weight: 500;
  background: var(--surface-muted);
}
tbody tr {
  cursor: pointer;
}
tbody tr:hover td {
  background: var(--brand-light);
}
tbody tr.on td {
  background: var(--brand-light);
}
.empty {
  text-align: center;
  color: var(--ink-faint);
  padding: 24px !important;
}
.mono {
  font-variant-numeric: tabular-nums;
  font-family: var(--mono, ui-monospace, monospace);
}
.up {
  color: var(--up, #c62828);
}
.down {
  color: var(--down, #2e7d32);
}
</style>

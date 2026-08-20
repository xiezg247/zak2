<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'
import AppShell from '../../../components/AppShell.vue'
import { jobsApi } from '../../../api/screener'
import {
  backtestApi,
  type BacktestRun,
  type BatchInfo,
  type OptimizeSummary,
  type StrategyInfo,
  type StrategyProfile,
} from '../../../api/backtest'
import BacktestProfilesBar from '../components/BacktestProfilesBar.vue'
import BacktestRunConfigPanel from '../components/BacktestRunConfigPanel.vue'
import BacktestResultPanel from '../components/BacktestResultPanel.vue'

const route = useRoute()

const strategies = ref<StrategyInfo[]>([])
const profiles = ref<StrategyProfile[]>([])
const runs = ref<BacktestRun[]>([])
const runsPage = ref(1)
const runsPages = ref(0)
const runsTotal = ref(0)
const batches = ref<BatchInfo[]>([])
const selected = ref<BacktestRun | null>(null)
const compare = ref<BacktestRun[]>([])
const optimizeSummary = ref<OptimizeSummary | null>(null)

const vtSymbol = ref('600519.SSE')
const batchSymbols = ref('')
const startDate = ref('2020-01-01')
const endDate = ref('2026-06-01')
const fast = ref(5)
const slow = ref(20)
const capital = ref(100000)
const strategy = ref('double_ma')
const interval = ref<'d' | '1m'>('d')
const maxTradingDays = ref(20)
const rate = ref(0.00045)
const slippage = ref(0)
const stampDuty = ref(0.0005)
const optFastSpace = ref('3,5,8,10')
const optSlowSpace = ref('10,20,30,60')

type ParamSpec = { key: string; label: string; min?: number; max?: number; step?: number }
const STRATEGY_PARAM_SPECS: Record<string, ParamSpec[]> = {
  trend_ma: [
    { key: 'adx_period', label: 'ADX 周期', min: 2 },
    { key: 'adx_threshold', label: 'ADX 阈值', min: 0, step: 0.1 },
    { key: 'trailing_stop_pct', label: '追踪止损', min: 0.01, max: 1, step: 0.01 },
  ],
  medium_swing: [
    { key: 'signal_period', label: '信号线', min: 2 },
    { key: 'trend_ma_window', label: '趋势均线', min: 10 },
  ],
  donchian: [
    { key: 'entry_window', label: '入场通道', min: 2 },
    { key: 'exit_window', label: '出场通道', min: 2 },
  ],
  rsi_reversal: [
    { key: 'rsi_period', label: 'RSI 周期', min: 2 },
    { key: 'oversold', label: '超卖阈值', min: 0 },
    { key: 'overbought', label: '超买阈值', min: 50, max: 100 },
  ],
  bollinger: [
    { key: 'boll_period', label: '布林周期', min: 2 },
    { key: 'boll_dev', label: '标准差倍数', min: 0.5, step: 0.1 },
  ],
  ma_band: [
    { key: 'ma_fast', label: '快线', min: 2 },
    { key: 'ma_mid', label: '中线', min: 2 },
    { key: 'ma_slow', label: '慢线', min: 2 },
    { key: 'ma_long', label: '长线', min: 2 },
  ],
  atr_breakout: [
    { key: 'channel_period', label: '通道周期', min: 2 },
    { key: 'atr_period', label: 'ATR 周期', min: 2 },
    { key: 'atr_mult', label: 'ATR 倍数', min: 0.5, step: 0.1 },
  ],
}

const paramsModel = reactive<Record<string, number>>({
  adx_period: 14,
  adx_threshold: 25,
  trailing_stop_pct: 0.12,
  signal_period: 9,
  trend_ma_window: 60,
  entry_window: 20,
  exit_window: 10,
  rsi_period: 14,
  oversold: 30,
  overbought: 70,
  boll_period: 20,
  boll_dev: 2,
  ma_fast: 5,
  ma_mid: 10,
  ma_slow: 20,
  ma_long: 60,
  channel_period: 20,
  atr_period: 14,
  atr_mult: 2,
})

const strategyParamSpecs = computed(() => STRATEGY_PARAM_SPECS[strategy.value] || [])

const running = ref(false)
const statusText = ref('')
const error = ref('')
const mode = ref<'single' | 'batch' | 'optimize'>('single')
const loading = ref(false)
const activeProfileId = ref('')

const subtitle = computed(
  () => `vnpy CTA · ${runsTotal.value} 条历史 · 策略画像 ${profiles.value.length}`,
)

function feePayload() {
  return {
    rate: rate.value,
    slippage: slippage.value,
    stamp_duty: stampDuty.value,
  }
}

function strategyParamsPayload() {
  const body: Record<string, unknown> = {}
  for (const spec of strategyParamSpecs.value) body[spec.key] = paramsModel[spec.key]
  return body
}

function intervalPayload() {
  const body: Record<string, unknown> = { interval: interval.value }
  if (interval.value === '1m') body.max_trading_days = maxTradingDays.value
  return body
}

function applyProfile(p: StrategyProfile) {
  fast.value = p.fast_window
  slow.value = p.slow_window
  capital.value = p.capital
  activeProfileId.value = p.profile_id
}

async function refresh() {
  error.value = ''
  const [s, p, b] = await Promise.all([
    backtestApi.strategies(),
    backtestApi.profiles(),
    backtestApi.batches(),
  ])
  strategies.value = s
  profiles.value = p
  batches.value = b
  await loadRuns()
}

async function loadRuns() {
  const r = await backtestApi.runsPage(runsPage.value, 20)
  runs.value = r.items
  runsTotal.value = r.total
  runsPages.value = r.pages
}

async function goRunsPage(p: number) {
  runsPage.value = p
  await loadRuns()
}

async function pollJob(jobId: string) {
  for (let i = 0; i < 180; i++) {
    const job = await jobsApi.get(jobId)
    statusText.value = `${job.status} · ${Math.round(job.progress * 100)}%`
    if (job.status === 'success') {
      await refresh()
      if (job.result_ref && job.result_ref.length === 32) {
        try {
          selected.value = await backtestApi.run(job.result_ref)
        } catch {
          /* batch may return batch_id */
        }
      }
      return
    }
    if (job.status === 'failed') throw new Error(job.error || '回测失败')
    await new Promise((r) => setTimeout(r, 500))
  }
  throw new Error('回测超时')
}

async function runSingle() {
  error.value = ''
  running.value = true
  try {
    const { job_id } = await backtestApi.start({
      vt_symbol: vtSymbol.value.trim(),
      strategy: strategy.value,
      start_date: startDate.value,
      end_date: endDate.value,
      fast_window: fast.value,
      slow_window: slow.value,
      capital: capital.value,
      ...intervalPayload(),
      ...feePayload(),
      ...strategyParamsPayload(),
    })
    await pollJob(job_id)
    statusText.value = '完成'
  } catch (e) {
    error.value = e instanceof Error ? e.message : '失败'
  } finally {
    running.value = false
  }
}

async function runBatch() {
  error.value = ''
  running.value = true
  try {
    const symbols = batchSymbols.value
      .split(/[\s,，]+/)
      .map((s) => s.trim())
      .filter(Boolean)
    if (!symbols.length) throw new Error('请填写标的列表')
    const { job_id, batch_id } = await backtestApi.startBatch({
      symbols,
      strategy: strategy.value,
      start_date: startDate.value,
      end_date: endDate.value,
      fast_window: fast.value,
      slow_window: slow.value,
      capital: capital.value,
      ...intervalPayload(),
      ...feePayload(),
      ...strategyParamsPayload(),
    })
    await pollJob(job_id)
    compare.value = await backtestApi.runs(batch_id)
    optimizeSummary.value = null
    statusText.value = `批次 ${batch_id.slice(0, 8)}… 完成`
  } catch (e) {
    error.value = e instanceof Error ? e.message : '失败'
  } finally {
    running.value = false
  }
}

function parseIntList(raw: string): number[] {
  return raw
    .split(/[\s,，]+/)
    .map((s) => Number(s.trim()))
    .filter((n) => Number.isFinite(n) && n > 0)
}

async function runOptimize() {
  error.value = ''
  running.value = true
  try {
    const fastList = parseIntList(optFastSpace.value)
    const slowList = parseIntList(optSlowSpace.value)
    if (!fastList.length || !slowList.length) throw new Error('请填写优化参数空间')
    const { job_id, batch_id } = await backtestApi.startOptimize({
      vt_symbol: vtSymbol.value.trim(),
      strategy: strategy.value,
      start_date: startDate.value,
      end_date: endDate.value,
      capital: capital.value,
      space: { fast_window: fastList, slow_window: slowList },
      objective: 'sharpe_ratio',
      ...intervalPayload(),
      ...feePayload(),
      ...strategyParamsPayload(),
    })
    await pollJob(job_id)
    optimizeSummary.value = await backtestApi.optimizeSummary(batch_id)
    compare.value = optimizeSummary.value.runs
    if (optimizeSummary.value.best) selected.value = optimizeSummary.value.best
    statusText.value = `优化 ${batch_id.slice(0, 8)}… 完成`
  } catch (e) {
    error.value = e instanceof Error ? e.message : '失败'
  } finally {
    running.value = false
  }
}

function startRun() {
  if (mode.value === 'single') return runSingle()
  if (mode.value === 'batch') return runBatch()
  return runOptimize()
}

async function openRun(id: string) {
  selected.value = await backtestApi.run(id)
}

async function openBatch(batchId: string) {
  compare.value = await backtestApi.runs(batchId)
}

onMounted(async () => {
  const q = route.query
  if (typeof q.vt_symbol === 'string' && q.vt_symbol.trim()) vtSymbol.value = q.vt_symbol.trim()
  if (typeof q.strategy === 'string' && q.strategy.trim()) strategy.value = q.strategy.trim()
  if (typeof q.fast_window === 'string' && Number(q.fast_window) > 0)
    fast.value = Number(q.fast_window)
  if (typeof q.slow_window === 'string' && Number(q.slow_window) > 0)
    slow.value = Number(q.slow_window)
  const extraKeys = [
    'adx_period',
    'adx_threshold',
    'trailing_stop_pct',
    'signal_period',
    'trend_ma_window',
    'entry_window',
    'exit_window',
    'rsi_period',
    'oversold',
    'overbought',
    'boll_period',
    'boll_dev',
    'ma_fast',
    'ma_mid',
    'ma_slow',
    'ma_long',
    'channel_period',
    'atr_period',
    'atr_mult',
  ]
  for (const key of extraKeys) {
    if (typeof q[key] === 'string' && Number(q[key]) > 0) paramsModel[key] = Number(q[key])
  }

  loading.value = true
  try {
    await refresh()
  } catch (e) {
    error.value = e instanceof Error ? e.message : '加载失败'
  } finally {
    loading.value = false
  }

  const jobId = typeof q.job_id === 'string' ? q.job_id.trim() : ''
  if (!jobId) return
  running.value = true
  error.value = ''
  try {
    await pollJob(jobId)
  } catch (e) {
    error.value = e instanceof Error ? e.message : '回测失败'
  } finally {
    running.value = false
  }
})
</script>

<template>
  <AppShell title="回测" :subtitle="subtitle" active="backtest">
    <div class="page">
      <p class="engine-tag muted">vnpy CTA · 日 K / 1 分钟</p>
      <BacktestProfilesBar
        :profiles="profiles"
        :active-profile-id="activeProfileId"
        @apply="applyProfile"
      />

      <div class="workspace">
        <BacktestRunConfigPanel
          v-model:mode="mode"
          v-model:strategy="strategy"
          v-model:interval="interval"
          v-model:max-trading-days="maxTradingDays"
          v-model:vt-symbol="vtSymbol"
          v-model:batch-symbols="batchSymbols"
          v-model:start-date="startDate"
          v-model:end-date="endDate"
          v-model:fast="fast"
          v-model:slow="slow"
          v-model:opt-fast-space="optFastSpace"
          v-model:opt-slow-space="optSlowSpace"
          v-model:capital="capital"
          v-model:rate="rate"
          v-model:slippage="slippage"
          v-model:stamp-duty="stampDuty"
          :strategies="strategies"
          :strategy-param-specs="strategyParamSpecs"
          :params-model="paramsModel"
          :runs="runs"
          :batches="batches"
          :selected="selected"
          :running="running"
          :status-text="statusText"
          :error="error"
          :loading="loading"
          :runs-page="runsPage"
          :runs-pages="runsPages"
          :runs-total="runsTotal"
          @start="startRun"
          @open-run="openRun"
          @open-batch="openBatch"
          @change-page="goRunsPage"
        />

        <BacktestResultPanel
          :selected="selected"
          :compare="compare"
          :optimize-summary="optimizeSummary"
          :loading="loading"
          @open-run="openRun"
        />
      </div>
    </div>
  </AppShell>
</template>

<style scoped>
.page {
  display: grid;
  gap: 12px;
  height: 100%;
  padding: 16px 24px 24px;
}
.workspace {
  display: grid;
  grid-template-columns: 300px 1fr;
  gap: 12px;
  min-height: 0;
  height: calc(100% - 36px);
}
.engine-tag {
  margin: 0;
  font-size: 0.85rem;
}
.muted {
  color: var(--muted);
  font-size: 0.85rem;
}
@media (max-width: 900px) {
  .workspace {
    grid-template-columns: 1fr;
  }
}
</style>

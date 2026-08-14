<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import AppShell from '../components/AppShell.vue'
import { jobsApi } from '../api/screener'
import {
  backtestApi,
  type BacktestRun,
  type BatchInfo,
  type OptimizeSummary,
  type StrategyInfo,
  type StrategyProfile,
} from '../api/backtest'

const strategies = ref<StrategyInfo[]>([])
const profiles = ref<StrategyProfile[]>([])
const runs = ref<BacktestRun[]>([])
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
const rate = ref(0.00045)
const slippage = ref(0)
const stampDuty = ref(0.0005)
const showFees = ref(false)
const showAllTrades = ref(false)
const optFastSpace = ref('3,5,8,10')
const optSlowSpace = ref('10,20,30,60')

const running = ref(false)
const statusText = ref('')
const error = ref('')
const mode = ref<'single' | 'batch' | 'optimize'>('single')
const listFilter = ref('')
const loading = ref(false)
const activeProfileId = ref('')

const subtitle = computed(
  () => `vnpy CTA · ${runs.value.length} 条历史 · 策略画像 ${profiles.value.length}`,
)

function feePayload() {
  return {
    rate: rate.value,
    slippage: slippage.value,
    stamp_duty: stampDuty.value,
  }
}

function numStat(key: string): number | null {
  const v = selected.value?.statistics?.[key]
  return typeof v === 'number' ? v : null
}

const displayedTrades = computed(() => {
  const trades = selected.value?.trades || []
  return showAllTrades.value ? trades : trades.slice(0, 40)
})

const showOpsLink = computed(() => /日 K|Ops|补全/.test(error.value))

function applyProfile(p: StrategyProfile) {
  fast.value = p.fast_window
  slow.value = p.slow_window
  capital.value = p.capital
  activeProfileId.value = p.profile_id
}

const displayedRuns = computed(() => {
  const q = listFilter.value.trim().toLowerCase()
  let list = runs.value
  if (q) {
    list = list.filter((r) => {
      const vt = (r.vt_symbol || '').toLowerCase()
      const st = (r.strategy || '').toLowerCase()
      return vt.includes(q) || st.includes(q)
    })
  }
  return list.slice(0, 30)
})

const displayedBatches = computed(() => {
  const q = listFilter.value.trim().toLowerCase()
  if (!q) return batches.value
  return batches.value.filter((b) => (b.strategy || '').toLowerCase().includes(q))
})

const spark = computed(() => {
  const curve = selected.value?.equity_curve || []
  if (curve.length < 2) return ''
  const vals = curve.map((p) => p.equity)
  const min = Math.min(...vals)
  const max = Math.max(...vals)
  const span = max - min || 1
  const w = 360
  const h = 120
  return vals
    .map((v, i) => {
      const x = (i / (vals.length - 1)) * w
      const y = h - ((v - min) / span) * (h - 8) - 4
      return `${x.toFixed(1)},${y.toFixed(1)}`
    })
    .join(' ')
})

async function refresh() {
  error.value = ''
  const [s, p, r, b] = await Promise.all([
    backtestApi.strategies(),
    backtestApi.profiles(),
    backtestApi.runs(),
    backtestApi.batches(),
  ])
  strategies.value = s
  profiles.value = p
  runs.value = r
  batches.value = b
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
      ...feePayload(),
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
      ...feePayload(),
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
      ...feePayload(),
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
  loading.value = true
  try {
    await refresh()
  } catch (e) {
    error.value = e instanceof Error ? e.message : '加载失败'
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <AppShell title="回测" :subtitle="subtitle" active="backtest">
    <div class="page">
      <p class="engine-tag muted">vnpy CTA 日 K 回测</p>
      <section class="profiles" v-if="profiles.length">
        <button
          v-for="p in profiles"
          :key="p.profile_id"
          type="button"
          class="chip"
          :class="{ on: activeProfileId === p.profile_id }"
          :title="p.description"
          @click="applyProfile(p)"
        >
          {{ p.name }}
        </button>
      </section>

      <div class="workspace">
        <aside class="left">
          <div class="tabs tabs3">
            <button type="button" :class="{ on: mode === 'single' }" @click="mode = 'single'">单票</button>
            <button type="button" :class="{ on: mode === 'batch' }" @click="mode = 'batch'">批量</button>
            <button type="button" :class="{ on: mode === 'optimize' }" @click="mode = 'optimize'">优化</button>
          </div>

          <label>
            策略
            <select v-model="strategy">
              <option v-for="s in strategies" :key="s.id" :value="s.id">{{ s.name }}</option>
            </select>
          </label>

          <label v-if="mode !== 'batch'">
            标的
            <input v-model="vtSymbol" placeholder="600519.SSE" />
          </label>
          <label v-else>
            标的列表
            <textarea v-model="batchSymbols" rows="4" placeholder="600519.SSE&#10;000001.SZSE" />
          </label>

          <div class="row2">
            <label>开始<input v-model="startDate" type="date" /></label>
            <label>结束<input v-model="endDate" type="date" /></label>
          </div>
          <div class="row2" v-if="mode !== 'optimize'">
            <label>快均线<input v-model.number="fast" type="number" min="2" /></label>
            <label>慢均线<input v-model.number="slow" type="number" min="3" /></label>
          </div>
          <template v-else>
            <label>快均线候选<input v-model="optFastSpace" placeholder="3,5,8,10" /></label>
            <label>慢均线候选<input v-model="optSlowSpace" placeholder="10,20,30,60" /></label>
          </template>
          <label>资金<input v-model.number="capital" type="number" step="1000" /></label>

          <button type="button" class="linkish" @click="showFees = !showFees">
            {{ showFees ? '收起费用' : '费用参数' }}
          </button>
          <div v-if="showFees" class="fees">
            <label>佣金 rate<input v-model.number="rate" type="number" step="0.0001" min="0" /></label>
            <label>滑点<input v-model.number="slippage" type="number" step="0.01" min="0" /></label>
            <label>印花税<input v-model.number="stampDuty" type="number" step="0.0001" min="0" /></label>
          </div>

          <button class="primary" type="button" :disabled="running" @click="startRun()">
            {{ running ? '回测中…' : mode === 'optimize' ? '开始优化' : '开始回测' }}
          </button>
          <p v-if="statusText" class="muted">{{ statusText }}</p>
          <p v-if="error" class="err">
            {{ error }}
            <RouterLink v-if="showOpsLink" to="/ops" class="draft-link">去 Ops 补全日 K</RouterLink>
          </p>

          <h3>历史</h3>
          <input
            v-if="runs.length"
            v-model="listFilter"
            class="filter"
            placeholder="过滤标的/策略"
          />
          <p v-if="loading" class="empty muted">加载中…</p>
          <template v-else>
            <p v-if="!runs.length" class="empty muted">暂无回测历史</p>
            <p v-else-if="!displayedRuns.length" class="empty muted">无匹配历史</p>
            <button
              v-for="r in displayedRuns"
              :key="r.id"
              type="button"
              class="hist"
              :class="{ on: selected?.id === r.id }"
              @click="openRun(r.id)"
            >
              <span>{{ r.vt_symbol }} · {{ r.strategy }}</span>
              <span class="muted">
                收益 {{ r.total_return != null ? r.total_return.toFixed(2) + '%' : '—' }}
                · {{ r.created_at }}
              </span>
            </button>
          </template>

          <h3 v-if="batches.length">批次对比</h3>
          <p
            v-if="batches.length && listFilter.trim() && !displayedBatches.length"
            class="empty muted"
          >
            无匹配批次
          </p>
          <button
            v-for="b in displayedBatches"
            :key="b.batch_id"
            type="button"
            class="hist"
            @click="openBatch(b.batch_id)"
          >
            <span>{{ b.strategy }} · {{ b.count }} 只</span>
            <span class="muted">{{ b.created_at }}</span>
          </button>
        </aside>

        <section class="right">
          <div v-if="selected" class="detail">
            <h2>
              {{ selected.vt_symbol }} · {{ selected.strategy }}
              <span class="muted" v-if="selected.engine"> · {{ selected.engine }}</span>
              <span class="muted" v-if="selected.status === 'failed'"> · 失败</span>
            </h2>
            <p v-if="selected.error_message" class="err">{{ selected.error_message }}</p>
            <div class="stats">
              <div class="stat">
                <div class="k">收益%</div>
                <div class="v" :class="{ up: (selected.total_return || 0) > 0, down: (selected.total_return || 0) < 0 }">
                  {{ selected.total_return != null ? selected.total_return.toFixed(2) : '—' }}
                </div>
              </div>
              <div class="stat">
                <div class="k">最大回撤%</div>
                <div class="v">{{ selected.max_drawdown != null ? selected.max_drawdown.toFixed(2) : '—' }}</div>
              </div>
              <div class="stat">
                <div class="k">夏普</div>
                <div class="v">{{ selected.sharpe_ratio != null ? selected.sharpe_ratio.toFixed(2) : '—' }}</div>
              </div>
              <div class="stat">
                <div class="k">成交</div>
                <div class="v">{{ selected.trade_count ?? '—' }}</div>
              </div>
              <div class="stat" v-if="numStat('annual_return') != null">
                <div class="k">年化%</div>
                <div class="v">{{ numStat('annual_return')!.toFixed(2) }}</div>
              </div>
              <div class="stat" v-if="numStat('return_std') != null">
                <div class="k">波动%</div>
                <div class="v">{{ numStat('return_std')!.toFixed(2) }}</div>
              </div>
              <div class="stat" v-if="numStat('win_rate') != null">
                <div class="k">胜率</div>
                <div class="v">{{ numStat('win_rate')!.toFixed(2) }}</div>
              </div>
              <div class="stat" v-if="numStat('profit_loss_ratio') != null">
                <div class="k">盈亏比</div>
                <div class="v">{{ numStat('profit_loss_ratio')!.toFixed(2) }}</div>
              </div>
            </div>
            <div class="chart" v-if="spark">
              <svg viewBox="0 0 360 120" preserveAspectRatio="none">
                <polyline fill="none" stroke="var(--brand)" stroke-width="2" :points="spark" />
              </svg>
            </div>
            <div class="table-wrap" v-if="selected.trades?.length">
              <div class="table-head">
                <span>成交明细</span>
                <button
                  v-if="selected.trades.length > 40"
                  type="button"
                  class="linkish"
                  @click="showAllTrades = !showAllTrades"
                >
                  {{ showAllTrades ? '收起' : '显示全部' }}
                </button>
              </div>
              <table>
                <thead>
                  <tr>
                    <th>时间</th>
                    <th>方向</th>
                    <th>价格</th>
                    <th>数量</th>
                    <th>盈亏</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="(t, i) in displayedTrades" :key="i">
                    <td class="mono">{{ t.datetime }}</td>
                    <td>{{ t.side || t.direction }}</td>
                    <td>{{ Number(t.price).toFixed(2) }}</td>
                    <td>{{ t.volume }}</td>
                    <td>{{ t.pnl != null ? Number(t.pnl).toFixed(2) : '—' }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          <div v-if="optimizeSummary?.best" class="compare">
            <h2>
              最优（{{ optimizeSummary.objective }}）
              <span class="muted">夏普 {{ optimizeSummary.best.sharpe_ratio?.toFixed(2) ?? '—' }}</span>
            </h2>
          </div>

          <div v-if="compare.length" class="compare">
            <h2>对比（{{ compare.length }}）</h2>
            <div class="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>标的</th>
                    <th>状态</th>
                    <th>收益%</th>
                    <th>回撤%</th>
                    <th>夏普</th>
                    <th>成交</th>
                    <th>参数</th>
                  </tr>
                </thead>
                <tbody>
                  <tr
                    v-for="r in compare"
                    :key="r.id"
                    @click="openRun(r.id)"
                    class="click"
                    :class="{ on: optimizeSummary?.best?.id === r.id }"
                  >
                    <td class="mono">{{ r.vt_symbol }}</td>
                    <td>{{ r.status === 'failed' ? r.error_message || '失败' : '成功' }}</td>
                    <td :class="{ up: (r.total_return || 0) > 0, down: (r.total_return || 0) < 0 }">
                      {{ r.total_return != null ? r.total_return.toFixed(2) : '—' }}
                    </td>
                    <td>{{ r.max_drawdown != null ? r.max_drawdown.toFixed(2) : '—' }}</td>
                    <td>{{ r.sharpe_ratio != null ? r.sharpe_ratio.toFixed(2) : '—' }}</td>
                    <td>{{ r.trade_count ?? '—' }}</td>
                    <td class="mono">
                      {{
                        r.params?.fast_window != null
                          ? `${r.params.fast_window}/${r.params.slow_window}`
                          : '—'
                      }}
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          <p v-if="!selected && !compare.length" class="empty muted">
            {{ loading ? '加载中…' : '运行回测或从左侧打开历史记录' }}
          </p>
        </section>
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
.profiles {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.chip {
  background: var(--bg-panel);
  border: 1px solid var(--border);
  border-radius: 999px;
  padding: 4px 10px;
  font-size: 0.8rem;
  color: var(--muted);
  cursor: pointer;
}
.chip.on {
  border-color: var(--accent);
  color: var(--text);
  font-weight: 500;
}
.draft-link {
  color: var(--brand);
  margin-left: 4px;
}
.workspace {
  display: grid;
  grid-template-columns: 300px 1fr;
  gap: 12px;
  min-height: 0;
  height: calc(100% - 36px);
}
.left,
.right {
  border: 1px solid var(--border);
  border-radius: 0.75rem;
  background: var(--bg-elevated);
  padding: 12px;
  overflow: auto;
  display: grid;
  gap: 10px;
  align-content: start;
}
.tabs {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 6px;
}
.tabs3 {
  grid-template-columns: 1fr 1fr 1fr;
}
.engine-tag {
  margin: 0;
  font-size: 0.85rem;
}
.linkish {
  background: transparent;
  border: none;
  color: var(--brand);
  text-align: left;
  padding: 0;
  cursor: pointer;
  font-size: 0.85rem;
}
.fees {
  display: grid;
  gap: 8px;
}
.table-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 10px;
  border-bottom: 1px solid var(--border);
  font-size: 0.85rem;
  color: var(--muted);
}
.tabs button {
  background: var(--bg);
  border: 1px solid var(--border);
  color: var(--muted);
  border-radius: 0.5rem;
  padding: 6px;
}
.tabs button.on {
  background: var(--brand-light);
  color: var(--brand);
  border-color: var(--brand-soft);
  font-weight: 500;
}
label {
  display: grid;
  gap: 4px;
  font-size: 0.8rem;
  color: var(--muted);
}
input,
select,
textarea {
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 0.5rem;
  color: var(--text);
  padding: 8px 10px;
}
.row2 {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}
.primary {
  background: var(--accent);
  border: none;
  color: var(--brand-foreground);
  border-radius: 0.5rem;
  padding: 10px;
  font-weight: 600;
}
.primary:disabled {
  opacity: 0.6;
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
h3 {
  margin: 8px 0 0;
  font-size: 0.9rem;
}
.filter {
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 0.5rem;
  color: var(--text);
  padding: 8px 10px;
  width: 100%;
}
.hist {
  text-align: left;
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 0.5rem;
  color: var(--text);
  padding: 8px;
  display: grid;
  gap: 2px;
}
.hist.on {
  border-color: var(--accent);
}
.stats {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 8px;
}
.stat {
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 0.5rem;
  padding: 8px 10px;
}
.k {
  color: var(--muted);
  font-size: 0.75rem;
}
.v {
  font-size: 1.1rem;
  font-weight: 600;
  margin-top: 2px;
}
.chart {
  border: 1px solid var(--border);
  border-radius: 0.75rem;
  background: var(--bg);
  padding: 10px;
}
.chart svg {
  width: 100%;
  height: 140px;
  display: block;
}
.table-wrap {
  border: 1px solid var(--border);
  border-radius: 0.75rem;
  overflow: auto;
  background: var(--bg);
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
  font-weight: 500;
}
.click {
  cursor: pointer;
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
  padding: 40px;
}
h2 {
  margin: 0;
  font-size: 1.1rem;
}
.detail,
.compare {
  display: grid;
  gap: 12px;
}
@media (max-width: 900px) {
  .workspace {
    grid-template-columns: 1fr;
  }
  .stats {
    grid-template-columns: 1fr 1fr;
  }
}
</style>

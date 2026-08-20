<script setup lang="ts">
import { computed, ref } from 'vue'
import { RouterLink } from 'vue-router'
import PagerBar from '../../../components/PagerBar.vue'
import { fmtDateTime } from '../../../lib/format'
import type { BacktestRun, BatchInfo, StrategyInfo } from '../../../api/backtest'

type ParamSpec = { key: string; label: string; min?: number; max?: number; step?: number }

const props = defineProps<{
  strategies: StrategyInfo[]
  strategyParamSpecs: ParamSpec[]
  paramsModel: Record<string, number>
  runs: BacktestRun[]
  batches: BatchInfo[]
  selected: BacktestRun | null
  running: boolean
  statusText: string
  error: string
  loading: boolean
  runsPage: number
  runsPages: number
  runsTotal: number
}>()

const mode = defineModel<'single' | 'batch' | 'optimize'>('mode', { required: true })
const strategy = defineModel<string>('strategy', { required: true })
const interval = defineModel<'d' | '1m'>('interval', { required: true })
const maxTradingDays = defineModel<number>('maxTradingDays', { required: true })
const vtSymbol = defineModel<string>('vtSymbol', { required: true })
const batchSymbols = defineModel<string>('batchSymbols', { required: true })
const startDate = defineModel<string>('startDate', { required: true })
const endDate = defineModel<string>('endDate', { required: true })
const fast = defineModel<number>('fast', { required: true })
const slow = defineModel<number>('slow', { required: true })
const optFastSpace = defineModel<string>('optFastSpace', { required: true })
const optSlowSpace = defineModel<string>('optSlowSpace', { required: true })
const capital = defineModel<number>('capital', { required: true })
const rate = defineModel<number>('rate', { required: true })
const slippage = defineModel<number>('slippage', { required: true })
const stampDuty = defineModel<number>('stampDuty', { required: true })

const emit = defineEmits<{
  start: []
  openRun: [id: string]
  openBatch: [batchId: string]
  changePage: [page: number]
}>()

const showFees = ref(false)
const listFilter = ref('')

const displayedRuns = computed(() => {
  const q = listFilter.value.trim().toLowerCase()
  let list = props.runs
  if (q) {
    list = list.filter((r) => {
      const vt = (r.vt_symbol || '').toLowerCase()
      const st = (r.strategy || '').toLowerCase()
      return vt.includes(q) || st.includes(q)
    })
  }
  return list
})

const displayedBatches = computed(() => {
  const q = listFilter.value.trim().toLowerCase()
  if (!q) return props.batches
  return props.batches.filter((b) => (b.strategy || '').toLowerCase().includes(q))
})

const showOpsLink = computed(() => /日 K|分钟 K|fill_focus_pool|关注池|Ops|补全/.test(props.error))

const opsLinkLabel = computed(() =>
  /分钟 K|fill_focus_pool|关注池/.test(props.error) ? '去 Ops 补全关注池 1m' : '去 Ops 补全日 K',
)
</script>

<template>
  <aside class="left">
    <div class="tabs tabs3">
      <button type="button" :class="{ on: mode === 'single' }" @click="mode = 'single'">
        单票
      </button>
      <button type="button" :class="{ on: mode === 'batch' }" @click="mode = 'batch'">批量</button>
      <button type="button" :class="{ on: mode === 'optimize' }" @click="mode = 'optimize'">
        优化
      </button>
    </div>

    <label>
      策略
      <select v-model="strategy">
        <option v-for="s in strategies" :key="s.id" :value="s.id">{{ s.name }}</option>
      </select>
    </label>

    <label>
      周期
      <select v-model="interval">
        <option value="d">日 K</option>
        <option value="1m">1 分钟</option>
      </select>
    </label>
    <p v-if="interval === '1m'" class="hint muted">
      均线窗口按分钟根计数；单次交易日默认最多 20（硬顶 60）。缺数据请先 Ops 跑
      fill_focus_pool_minute。
    </p>
    <label v-if="interval === '1m'">
      最多交易日
      <input v-model.number="maxTradingDays" type="number" min="1" max="60" />
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
    <div v-if="mode !== 'optimize'" class="row2">
      <label>
        {{ strategy === 'medium_swing' ? 'MACD 快线' : '快均线' }}
        <input v-model.number="fast" type="number" min="2" />
      </label>
      <label>
        {{ strategy === 'medium_swing' ? 'MACD 慢线' : '慢均线' }}
        <input v-model.number="slow" type="number" min="3" />
      </label>
    </div>
    <template v-else>
      <label>快均线候选<input v-model="optFastSpace" placeholder="3,5,8,10" /></label>
      <label>慢均线候选<input v-model="optSlowSpace" placeholder="10,20,30,60" /></label>
    </template>
    <div v-if="strategyParamSpecs.length && mode !== 'optimize'" class="strategy-params">
      <label v-for="p in strategyParamSpecs" :key="p.key">
        {{ p.label }}
        <input
          v-model.number="paramsModel[p.key]"
          type="number"
          :min="p.min"
          :max="p.max"
          :step="p.step ?? 1"
        />
      </label>
    </div>
    <p v-if="strategy === 'medium_swing'" class="hint muted">
      MACD 金叉且站上趋势均线买入；死叉或跌破趋势均线卖出。
    </p>
    <label>资金<input v-model.number="capital" type="number" step="1000" /></label>

    <button type="button" class="linkish" @click="showFees = !showFees">
      {{ showFees ? '收起费用' : '费用参数' }}
    </button>
    <div v-if="showFees" class="fees">
      <label>佣金 rate<input v-model.number="rate" type="number" step="0.0001" min="0" /></label>
      <label>滑点<input v-model.number="slippage" type="number" step="0.01" min="0" /></label>
      <label>印花税<input v-model.number="stampDuty" type="number" step="0.0001" min="0" /></label>
    </div>

    <button class="primary" type="button" :disabled="running" @click="emit('start')">
      {{ running ? '回测中…' : mode === 'optimize' ? '开始优化' : '开始回测' }}
    </button>
    <p v-if="statusText" class="muted">{{ statusText }}</p>
    <p v-if="error" class="err">
      {{ error }}
      <RouterLink v-if="showOpsLink" to="/ops" class="draft-link">{{ opsLinkLabel }}</RouterLink>
    </p>

    <h3>历史</h3>
    <input v-if="runs.length" v-model="listFilter" class="filter" placeholder="过滤标的/策略" />
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
        @click="emit('openRun', r.id)"
      >
        <span>{{ r.vt_symbol }} · {{ r.strategy }}</span>
        <span class="muted">
          收益 {{ r.total_return != null ? r.total_return.toFixed(2) + '%' : '—' }} ·
          {{ fmtDateTime(r.created_at) }}
        </span>
      </button>
      <PagerBar :page="runsPage" :pages="runsPages" :total="runsTotal" @change="emit('changePage', $event)" />
    </template>

    <h3 v-if="batches.length">批次对比</h3>
    <p v-if="batches.length && listFilter.trim() && !displayedBatches.length" class="empty muted">
      无匹配批次
    </p>
    <button
      v-for="b in displayedBatches"
      :key="b.batch_id"
      type="button"
      class="hist"
      @click="emit('openBatch', b.batch_id)"
    >
      <span>{{ b.strategy }} · {{ b.count }} 只</span>
      <span class="muted">{{ fmtDateTime(b.created_at) }}</span>
    </button>
  </aside>
</template>

<style scoped>
.left {
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
.draft-link {
  color: var(--brand);
  margin-left: 4px;
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
.strategy-params {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.strategy-params label {
  flex: 1 1 40%;
  min-width: 0;
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
.hint {
  margin: 0;
  line-height: 1.4;
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
.empty {
  text-align: center;
  padding: 40px;
}
</style>

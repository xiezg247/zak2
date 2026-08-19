<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import AppShell from '../components/AppShell.vue'
import CandleChart from '../components/CandleChart.vue'
import StockAnalysisModal from '../components/StockAnalysisModal.vue'
import { marketApi, type EmotionThresholds, type MarketOverview, type RankRow } from '../api/market'
import { watchlistApi, type Bar, type Fundamentals } from '../api/watchlist'
import { POLL_FAST_MS, POLL_SLOW_MS, useQuoteNotify } from '../composables/useQuoteNotify'
import { useStockAnalysis } from '../composables/useStockAnalysis'

const analysis = useStockAnalysis()

const overview = ref<MarketOverview | null>(null)
const field = ref('change_pct')
// 0 表示全部（后端全量上限以内）
const rankLimit = ref(50)
const rankLimitChoices = [50, 100, 200, 500, 0]
const ranks = ref<RankRow[]>([])
const error = ref('')
const loading = ref(false)
const autoRefresh = ref(true)
const chartVt = ref('')
const chartBars = ref<Bar[]>([])
const chartBarsError = ref('')
const chartBarsLoading = ref(false)
const barInterval = ref<'d' | '1m'>('d')
const barLimitDaily = ref(90)
const barLimit1m = ref(480)

const barLimit = computed({
  get: () => (barInterval.value === '1m' ? barLimit1m.value : barLimitDaily.value),
  set: (n: number) => {
    if (barInterval.value === '1m') barLimit1m.value = n
    else barLimitDaily.value = n
  },
})

const barLimitChoices = computed(() =>
  barInterval.value === '1m' ? [240, 480, 1200] : [60, 90, 120],
)

// 0 表示全部：请求一个覆盖全市场的上限（后端 le=20000）
const FULL_RANK_TOP = 20000
// 搜索关键词激活时强制全量拉取，确保过滤/搜索覆盖全部标的
const searchActive = computed(() => listFilter.value.trim() !== '')
function rankTopN(): number {
  if (searchActive.value) return FULL_RANK_TOP
  return rankLimit.value === 0 ? FULL_RANK_TOP : rankLimit.value
}
function rankLimitLabel(n: number): string {
  return n === 0 ? '全部' : String(n)
}
const watchSet = ref<Set<string>>(new Set())
const fundVt = ref('')
const fundData = ref<Fundamentals | null>(null)
const fundLoading = ref(false)
const fundError = ref('')
// 休市时数据静止，无需高频拉取；慢轮询兜底以便开市后自动切回
const CLOSED_POLL_MS = 5 * 60_000
const thresholdsOpen = ref(false)
const cycleInputsOpen = ref(false)
const thresholdsSectionEl = ref<HTMLElement | null>(null)
const thresholdsDraft = ref<EmotionThresholds | null>(null)
const thresholdsBusy = ref(false)
const thresholdsErr = ref('')
const thresholdsMsg = ref('')
let timer: number | undefined

const thresholdFields: {
  key: keyof Omit<EmotionThresholds, 'is_default'>
  label: string
  step?: number
  min?: number
  max?: number
  kind?: 'bool'
}[] = [
  { key: 'recession_limit_down', label: '衰退跌停数', step: 1, min: 0 },
  { key: 'ice_limit_down', label: '冰点跌停数', step: 1, min: 0 },
  { key: 'ice_max_boards', label: '冰点最高板', step: 1, min: 0 },
  { key: 'ice_up_ratio_max', label: '冰点上涨比上限', step: 0.01, min: 0, max: 1 },
  { key: 'climax_limit_up', label: '高潮涨停数', step: 1, min: 0 },
  { key: 'climax_ladder_depth', label: '高潮梯队深度', step: 1, min: 0 },
  { key: 'startup_limit_up', label: '启动涨停数', step: 1, min: 0 },
  { key: 'startup_max_boards', label: '启动最高板', step: 1, min: 0 },
  { key: 'divergence_limit_up_min', label: '分歧涨停下限', step: 1, min: 0 },
  { key: 'divergence_limit_spread', label: '分歧板差', step: 1, min: 0 },
  { key: 'fear_greed_overheat', label: '恐贪过热', step: 1, min: 0, max: 100 },
  { key: 'recession_break_rate', label: '衰退炸板率', step: 0.01, min: 0, max: 1 },
  { key: 'amount_floor_yuan', label: '成交额下限(元)', step: 1e8, min: 0 },
  { key: 'hysteresis_enabled', label: '滞回', kind: 'bool' },
]

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

function restartPoll() {
  if (timer) window.clearInterval(timer)
  timer = window.setInterval(tick, pollIntervalMs())
}

watch(connected, () => restartPoll())
watch(
  () => overview.value?.is_trading,
  () => restartPoll(),
)

const fields = [
  { id: 'change_pct', label: '涨幅', col: '涨幅%' },
  { id: 'turnover_rate', label: '换手', col: '换手%' },
  { id: 'amount', label: '成交额', col: '成交额' },
  { id: 'volume_ratio', label: '量比', col: '量比' },
]

const fieldMeta = computed(() => fields.find((f) => f.id === field.value) || fields[0])

type SortKey =
  | 'last_price'
  | 'change_pct'
  | 'change_amount'
  | 'turnover_rate'
  | 'amount'
  | 'volume_ratio'
  | 'amplitude'
  | 'total_mv'
  | null

const listFilter = ref('')
const sortKey = ref<SortKey>(null)
const sortDir = ref<'asc' | 'desc'>('desc')

function cmpNullable(
  a: number | null | undefined,
  b: number | null | undefined,
  dir: 'asc' | 'desc',
): number {
  const aMissing = a == null || Number.isNaN(a)
  const bMissing = b == null || Number.isNaN(b)
  if (aMissing && bMissing) return 0
  if (aMissing) return 1
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

function sortMark(key: Exclude<SortKey, null>): string {
  if (sortKey.value !== key) return ''
  return sortDir.value === 'asc' ? ' ▲' : ' ▼'
}

const scoreSortKey = computed((): Exclude<SortKey, null> | null => {
  const id = field.value
  if (id === 'change_pct') return null
  if (id === 'turnover_rate' || id === 'amount' || id === 'volume_ratio') {
    return id
  }
  return null
})

// —— 板块过滤 ——
type BoardKey = 'all' | 'main' | 'gem' | 'star' | 'bse'
const boardFilter = ref<BoardKey>('all')
const boardOptions: { key: BoardKey; label: string }[] = [
  { key: 'all', label: '全部' },
  { key: 'main', label: '沪深主板' },
  { key: 'gem', label: '创业板' },
  { key: 'star', label: '科创板' },
  { key: 'bse', label: '北交所' },
]

function boardOf(r: RankRow): BoardKey {
  const vt = (r.vt_symbol || '').toUpperCase()
  const code = vt.split('.')[0] || ''
  if (vt.endsWith('.SSE')) return code.startsWith('68') ? 'star' : 'main'
  if (vt.endsWith('.SZSE')) return code.startsWith('30') ? 'gem' : 'main'
  if (vt.endsWith('.BSE')) return 'bse'
  return 'all'
}

const displayedRanks = computed(() => {
  const q = listFilter.value.trim().toLowerCase()
  let list = ranks.value
  if (boardFilter.value !== 'all') {
    list = list.filter((r) => boardOf(r) === boardFilter.value)
  }
  if (q) {
    list = list.filter((r) => {
      const vt = (r.vt_symbol || '').toLowerCase()
      const name = (r.name || '').toLowerCase()
      return vt.includes(q) || name.includes(q)
    })
  }
  const key = sortKey.value
  if (!key) return list
  const dir = sortDir.value
  return [...list].sort((a, b) => cmpNullable(a[key], b[key], dir))
})

// —— 虚拟滚动 ——
// 固定行高 + 滚动容器测高，只渲染可视窗口内的行；列表 < 阈值时退化为普通渲染
const ROW_H = 33
const OVERSCAN = 12
const VIRTUAL_MIN = 300
const tableWrapEl = ref<HTMLElement | null>(null)
const scrollTop = ref(0)
const viewportH = ref(0)
const rowH = ref(ROW_H)

const useVirtual = computed(
  () => (ranks.value.length > VIRTUAL_MIN && displayedRanks.value.length > VIRTUAL_MIN) || false,
)

const virtualWindow = computed(() => {
  const list = displayedRanks.value
  const total = list.length
  if (total === 0) return { rows: [], padTop: 0, padBottom: 0, offset: 0 }
  const h = rowH.value || ROW_H
  const start = Math.max(0, Math.floor(scrollTop.value / h) - OVERSCAN)
  const end = Math.min(total, Math.ceil((scrollTop.value + viewportH.value) / h) + OVERSCAN)
  return {
    rows: list.slice(start, end),
    padTop: start * h,
    padBottom: Math.max(0, (total - end) * h),
    offset: start,
  }
})

function measureTable() {
  const el = tableWrapEl.value
  if (!el) return
  viewportH.value = el.clientHeight
  const tr = el.querySelector('tbody tr:not(.vpad)')
  if (tr) rowH.value = tr.getBoundingClientRect().height || ROW_H
}

function onTableScroll() {
  scrollTop.value = tableWrapEl.value?.scrollTop || 0
}

watch(displayedRanks, () => {
  scrollTop.value = 0
  void nextTick(() => measureTable())
})

// 搜索关键词在「空 ↔ 非空」间切换时，需要重新拉取（全量 vs 档位量）数据
watch(searchActive, (active, prev) => {
  if (active === prev) return
  scrollTop.value = 0
  void load(true)
})

// 接口未返回对应字段（或全为空值）时隐藏列；有数据则展示
const condCols = [
  'change_pct',
  'change_amount',
  'turnover_rate',
  'volume_ratio',
  'total_mv',
  'industry',
  'trade_time',
  'amplitude',
] as const

type CondCol = (typeof condCols)[number]

function colHasValue(r: RankRow, key: CondCol): boolean {
  const v = r[key]
  if (typeof v === 'string') return v.trim() !== ''
  return v != null && !Number.isNaN(v) && v !== 0
}

const colVisible = computed(() => {
  const map = {} as Record<CondCol, boolean>
  for (const key of condCols) map[key] = ranks.value.some((r) => colHasValue(r, key))
  return map
})

// 空态行 colspan：固定列 #/代码/名称/现价/分数字段/成交额/操作 = 7，加上可见的条件列
const emptyColspan = computed(() => 7 + condCols.filter((k) => colVisible.value[k]).length)

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

function posPct(cycle: NonNullable<MarketOverview['emotion_cycle']>): string {
  const lo = Math.round(cycle.position_pct_min * 100)
  const hi = Math.round(cycle.position_pct_max * 100)
  return `${lo}–${hi}%`
}

function openThresholdsFromCard() {
  thresholdsOpen.value = true
  void nextTick(() => {
    thresholdsSectionEl.value?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
  })
}

function scoreLabel(r: RankRow): string {
  const id = field.value
  if (id === 'change_pct') return r.change_pct != null ? r.change_pct.toFixed(2) : '—'
  if (id === 'turnover_rate') return r.turnover_rate != null ? r.turnover_rate.toFixed(2) : '—'
  if (id === 'amount') return r.amount != null ? (r.amount / 1e8).toFixed(2) + '亿' : '—'
  if (id === 'volume_ratio') return r.volume_ratio != null ? r.volume_ratio.toFixed(2) : '—'
  return r.score.toFixed(2)
}

function fmtNum(v: number | null | undefined, digits = 2): string {
  if (v == null || Number.isNaN(v)) return '—'
  return v.toFixed(digits)
}

function fmtAmount(v: number | null | undefined): string {
  if (v == null || Number.isNaN(v) || v <= 0) return '—'
  if (v >= 1e8) return (v / 1e8).toFixed(2) + '亿'
  if (v >= 1e4) return (v / 1e4).toFixed(1) + '万'
  return v.toFixed(0)
}

function fmtSigned(v: number | null | undefined): string {
  if (v == null || Number.isNaN(v)) return '—'
  return (v > 0 ? '+' : '') + v.toFixed(2)
}

function fmtMv(v: number | null | undefined): string {
  // 万元为单位（与 Tushare daily_basic 一致）
  if (v == null || Number.isNaN(v) || v <= 0) return '—'
  if (v >= 1e8) return (v / 1e8).toFixed(2) + '万亿'
  if (v >= 1e4) return (v / 1e4).toFixed(2) + '亿'
  return v.toFixed(0) + '万'
}

function fmtYmd(raw: string | null | undefined): string {
  const s = (raw || '').trim()
  if (!s) return '—'
  if (/^\d{8}$/.test(s)) return `${s.slice(0, 4)}-${s.slice(4, 6)}-${s.slice(6, 8)}`
  return s
}

function fmtMoney(n: number | null | undefined): string {
  if (n == null || Number.isNaN(n)) return '—'
  if (Math.abs(n) >= 1e8) return `${(n / 1e8).toFixed(2)} 亿`
  if (Math.abs(n) >= 1e4) return `${(n / 1e4).toFixed(2)} 万`
  return n.toFixed(2)
}

function fmtRatioPct(n: number | null | undefined): string {
  if (n == null || Number.isNaN(n)) return '—'
  return `${(n * 100).toFixed(1)}%`
}

function fmtTime(raw: string | null | undefined): string {
  if (!raw) return '—'
  // TickFlow trade_time 形如 "HH:MM:SS"，取时分
  return raw.slice(0, 5)
}

function applyThresholds(t: EmotionThresholds) {
  thresholdsDraft.value = { ...t }
}

async function loadThresholds() {
  thresholdsErr.value = ''
  thresholdsMsg.value = ''
  try {
    applyThresholds(await marketApi.emotionThresholds())
  } catch (e) {
    thresholdsErr.value = e instanceof Error ? e.message : '阈值加载失败'
  }
}

async function saveThresholds() {
  if (!thresholdsDraft.value) return
  thresholdsBusy.value = true
  thresholdsErr.value = ''
  thresholdsMsg.value = ''
  const { is_default: _, ...body } = thresholdsDraft.value
  try {
    const out = await marketApi.putEmotionThresholds(body)
    applyThresholds(out)
    thresholdsMsg.value = '阈值已保存'
    await load(true)
  } catch (e) {
    thresholdsErr.value = e instanceof Error ? e.message : '保存失败'
  } finally {
    thresholdsBusy.value = false
  }
}

async function resetThresholds() {
  thresholdsBusy.value = true
  thresholdsErr.value = ''
  thresholdsMsg.value = ''
  try {
    const out = await marketApi.resetEmotionThresholds()
    applyThresholds(out)
    thresholdsMsg.value = '已恢复默认阈值'
    await load(true)
  } catch (e) {
    thresholdsErr.value = e instanceof Error ? e.message : '恢复失败'
  } finally {
    thresholdsBusy.value = false
  }
}

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
  chartBars.value = []
  chartBarsError.value = ''
  chartBarsLoading.value = false
  try {
    ranks.value = await marketApi.ranks(field.value, rankTopN())
  } catch (e) {
    ranks.value = []
    error.value = e instanceof Error ? e.message : '排行加载失败'
  }
}

async function loadChartBars(vt: string) {
  chartBarsError.value = ''
  chartBars.value = []
  if (!vt) {
    chartBarsLoading.value = false
    return
  }
  chartBarsLoading.value = true
  try {
    const resp = await watchlistApi.bars(vt, barInterval.value, barLimit.value)
    chartBars.value = resp.bars
  } catch (e) {
    chartBarsError.value = e instanceof Error ? e.message : '无 K 线'
  } finally {
    chartBarsLoading.value = false
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

async function openFund(r: RankRow) {
  fundVt.value = r.vt_symbol
  fundError.value = ''
  fundData.value = null
  fundLoading.value = true
  try {
    fundData.value = await watchlistApi.fundamentals(r.vt_symbol)
  } catch (e) {
    fundError.value = e instanceof Error ? e.message : '基本面加载失败'
  } finally {
    fundLoading.value = false
  }
}

function closeFund() {
  fundVt.value = ''
  fundData.value = null
  fundError.value = ''
  fundLoading.value = false
}

const fundRow = computed(() => ranks.value.find((r) => r.vt_symbol === fundVt.value) || null)

function openChart(r: RankRow) {
  chartVt.value = r.vt_symbol
  chartBarsError.value = ''
  chartBars.value = []
  void loadChartBars(r.vt_symbol)
}

function closeChart() {
  chartVt.value = ''
  chartBars.value = []
  chartBarsError.value = ''
  chartBarsLoading.value = false
}

const chartRow = computed(() => ranks.value.find((r) => r.vt_symbol === chartVt.value) || null)

function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape') {
    if (chartVt.value) closeChart()
    else if (fundVt.value) closeFund()
  }
}

function tick() {
  if (!autoRefresh.value || document.hidden) return
  void load(true)
}

watch(field, () => {
  const sk = sortKey.value
  if (sk && sk !== 'last_price' && sk !== 'change_pct' && sk !== field.value) {
    sortKey.value = null
  }
  void onField()
})

watch(thresholdsOpen, (open) => {
  if (open) void loadThresholds()
})

watch([barLimit, barInterval], () => {
  if (chartVt.value) void loadChartBars(chartVt.value)
})

watch(rankLimit, () => {
  scrollTop.value = 0
  void load(true)
})

let resizeObs: ResizeObserver | undefined

onMounted(() => {
  void load()
  void loadWatchSet()
  restartPoll()
  document.addEventListener('keydown', onKeydown)
  void nextTick(() => measureTable())
  resizeObs = new ResizeObserver(() => measureTable())
  if (tableWrapEl.value) resizeObs.observe(tableWrapEl.value)
})

onUnmounted(() => {
  resizeObs?.disconnect()
  document.removeEventListener('keydown', onKeydown)
  if (timer) window.clearInterval(timer)
})
</script>

<template>
  <AppShell title="市场" :subtitle="subtitle" active="market">
    <div class="page">
      <section v-if="overview" class="cards">
        <div class="card">
          <div class="k">Redis</div>
          <div class="v status-line">
            <span class="dot" :class="overview.redis_available ? 'ok' : 'warn'"></span>
            {{ overview.redis_available ? '在线' : '离线' }} · {{ overview.quote_count }} 只
            <span class="trading-badge" :class="overview.is_trading ? 'on' : 'off'">
              {{ overview.is_trading ? '交易中' : '休市' }}
            </span>
          </div>
          <div class="s muted">{{ overview.updated_at || '—' }}</div>
        </div>
        <div v-if="overview.emotion_cycle" class="card cycle-card">
          <div class="k">情绪周期</div>
          <div class="cycle-head">
            <div class="v">{{ overview.emotion_cycle.stage_label }}</div>
            <span
              class="cycle-gate"
              :class="overview.emotion_cycle.allow_new_positions ? 'ok' : 'warn'"
            >
              {{ overview.emotion_cycle.allow_new_positions ? '可新开' : '不宜新开' }}
            </span>
          </div>
          <div class="s muted">
            仓位建议 {{ posPct(overview.emotion_cycle) }}
            <template v-if="overview.emotion_cycle.allowed_mode_labels.length">
              · {{ overview.emotion_cycle.allowed_mode_labels.join('/') }}
            </template>
          </div>
          <div v-for="(w, i) in overview.emotion_cycle.warnings" :key="i" class="s warn">
            {{ w }}
          </div>
          <div class="cycle-actions">
            <button
              type="button"
              class="ghost tiny-btn"
              @click="cycleInputsOpen = !cycleInputsOpen"
            >
              {{ cycleInputsOpen ? '收起明细' : '明细' }}
            </button>
            <button type="button" class="ghost tiny-btn" @click="openThresholdsFromCard">
              阈值
            </button>
          </div>
          <div v-if="cycleInputsOpen && overview.emotion_cycle.inputs" class="s muted">
            涨停 {{ overview.emotion_cycle.inputs.limit_up_count ?? '—' }} · 跌停
            {{ overview.emotion_cycle.inputs.limit_down_count ?? '—' }} · 最高板
            {{ overview.emotion_cycle.inputs.max_limit_times ?? '—' }}
            <template v-if="overview.emotion_cycle.inputs.fear_greed_index != null">
              · 恐贪≈{{ overview.emotion_cycle.inputs.fear_greed_index }}
            </template>
            <template v-if="overview.emotion_cycle.inputs.index_above_ma5 === true">
              · 站上MA5</template
            >
            <template v-else-if="overview.emotion_cycle.inputs.index_above_ma5 === false">
              · 跌破MA5</template
            >
          </div>
        </div>
        <div v-else class="card">
          <div class="k">情绪周期</div>
          <div class="v muted">暂无数据</div>
          <p class="s muted empty-cycle-hint">
            可到 Ops 执行 warm_market_summary 预热。
            <RouterLink to="/ops" class="draft-link">去 Ops</RouterLink>
          </p>
        </div>
      </section>

      <section v-if="overview?.emotion_cycle" ref="thresholdsSectionEl" class="thresholds-section">
        <div class="thresholds-head">
          <div>
            <strong>判定阈值</strong>
            <span v-if="thresholdsDraft" class="muted tag">
              {{ thresholdsDraft.is_default ? '默认' : '已自定义' }}
            </span>
          </div>
          <button class="ghost tiny-btn" type="button" @click="thresholdsOpen = !thresholdsOpen">
            {{ thresholdsOpen ? '收起' : '展开' }}
          </button>
        </div>
        <div v-if="thresholdsOpen" class="thresholds-panel">
          <p class="muted thresholds-hint">
            全局 meta 持久化；保存后失效短 TTL 缓存并刷新情绪周期。
          </p>
          <div v-if="thresholdsDraft" class="thresholds-grid">
            <div v-for="f in thresholdFields" :key="f.key" class="threshold-row">
              <label :for="`th-${f.key}`">{{ f.label }}</label>
              <input
                v-if="f.kind === 'bool'"
                :id="`th-${f.key}`"
                v-model="thresholdsDraft[f.key]"
                type="checkbox"
                :disabled="thresholdsBusy"
              />
              <input
                v-else
                :id="`th-${f.key}`"
                v-model.number="thresholdsDraft[f.key]"
                type="number"
                :step="f.step ?? 1"
                :min="f.min"
                :max="f.max"
                :disabled="thresholdsBusy"
              />
            </div>
          </div>
          <p v-else-if="!thresholdsErr" class="muted">加载中…</p>
          <p v-if="thresholdsErr" class="err">{{ thresholdsErr }}</p>
          <p v-if="thresholdsMsg" class="ok">{{ thresholdsMsg }}</p>
          <div class="thresholds-actions">
            <button
              class="primary"
              type="button"
              :disabled="thresholdsBusy || !thresholdsDraft"
              @click="saveThresholds"
            >
              保存
            </button>
            <button class="ghost" type="button" :disabled="thresholdsBusy" @click="resetThresholds">
              恢复默认
            </button>
          </div>
        </div>
      </section>

      <div class="toolbar">
        <div class="tabs">
          <button
            v-for="f in fields"
            :key="f.id"
            type="button"
            :class="{ on: field === f.id }"
            @click="field = f.id"
          >
            {{ f.label }}
          </button>
        </div>
        <div class="actions">
          <label class="auto">
            <input v-model="autoRefresh" type="checkbox" />
            {{ refreshLabel }}
          </label>
          <div class="limits">
            <button
              v-for="n in rankLimitChoices"
              :key="n"
              type="button"
              class="chip"
              :class="{ on: searchActive ? n === 0 : rankLimit === n }"
              :disabled="searchActive"
              @click="rankLimit = n"
            >
              {{ rankLimitLabel(n) }}
            </button>
          </div>
          <button class="ghost" type="button" :disabled="loading" @click="load()">刷新</button>
          <RouterLink to="/sectors" class="cross-link">板块资金 →</RouterLink>
        </div>
      </div>

      <p v-if="error" class="err">{{ error }}</p>

      <div v-if="ranks.length" class="filter-row">
        <input v-model="listFilter" placeholder="过滤代码/名称" />
        <div class="board-filter">
          <button
            v-for="b in boardOptions"
            :key="b.key"
            type="button"
            class="chip"
            :class="{ on: boardFilter === b.key }"
            @click="boardFilter = b.key"
          >
            {{ b.label }}
          </button>
        </div>
        <span class="muted count-hint"
          >{{ displayedRanks.length }} 只<span v-if="searchActive" class="search-all-tag"
            >全量搜索</span
          ></span
        >
        <button type="button" class="ghost" :class="{ on: !sortKey }" @click="clearSort">
          默认序
        </button>
      </div>

      <div class="split">
        <div ref="tableWrapEl" class="table-wrap" @scroll.passive="onTableScroll">
          <p v-if="ranks.length && !displayedRanks.length" class="muted empty-hint">无匹配标的</p>
          <table v-else>
            <thead>
              <tr>
                <th>#</th>
                <th>代码</th>
                <th>名称</th>
                <th class="sortable" @click="toggleSort('last_price')">
                  现价{{ sortMark('last_price') }}
                </th>
                <th v-if="colVisible.change_pct" class="sortable" @click="toggleSort('change_pct')">
                  涨幅%{{ sortMark('change_pct') }}
                </th>
                <th v-if="colVisible.change_amount" class="sortable" @click="toggleSort('change_amount')">
                  涨跌额{{ sortMark('change_amount') }}
                </th>
                <th v-if="scoreSortKey" class="sortable" @click="toggleSort(scoreSortKey)">
                  {{ fieldMeta.col }}{{ sortMark(scoreSortKey) }}
                </th>
                <th v-else>{{ fieldMeta.col }}</th>
                <th v-if="colVisible.turnover_rate" class="sortable" @click="toggleSort('turnover_rate')">
                  换手%{{ sortMark('turnover_rate') }}
                </th>
                <th v-if="colVisible.volume_ratio" class="sortable" @click="toggleSort('volume_ratio')">
                  量比{{ sortMark('volume_ratio') }}
                </th>
                <th v-if="colVisible.total_mv" class="sortable" @click="toggleSort('total_mv')">
                  总市值{{ sortMark('total_mv') }}
                </th>
                <th v-if="colVisible.industry">行业</th>
                <th v-if="colVisible.trade_time">时间</th>
                <th v-if="colVisible.amplitude" class="sortable" @click="toggleSort('amplitude')">
                  振幅%{{ sortMark('amplitude') }}
                </th>
                <th class="sortable" @click="toggleSort('amount')">成交额{{ sortMark('amount') }}</th>
                <th class="ops">操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-if="useVirtual && virtualWindow.padTop" class="vpad">
                <td :colspan="emptyColspan" :style="{ height: virtualWindow.padTop + 'px' }"></td>
              </tr>
              <template
                v-for="(r, j) in useVirtual ? virtualWindow.rows : displayedRanks"
                :key="r.tf_symbol"
              >
                <tr>
                  <td>
                    <span class="rank-badge" :class="'rank-' + ((useVirtual ? virtualWindow.offset + j : j) + 1)">{{
                      (useVirtual ? virtualWindow.offset + j : j) + 1
                    }}</span>
                  </td>
                  <td class="mono">{{ r.vt_symbol }}</td>
                  <td>{{ r.name || '—' }}</td>
                  <td>{{ r.last_price != null ? r.last_price.toFixed(2) : '—' }}</td>
                  <td
                    v-if="colVisible.change_pct"
                    :class="{ up: (r.change_pct || 0) > 0, down: (r.change_pct || 0) < 0 }"
                  >
                    {{ r.change_pct != null ? r.change_pct.toFixed(2) : '—' }}
                  </td>
                  <td
                    v-if="colVisible.change_amount"
                    :class="{ up: (r.change_amount || 0) > 0, down: (r.change_amount || 0) < 0 }"
                  >
                    {{ fmtSigned(r.change_amount) }}
                  </td>
                  <td>{{ scoreLabel(r) }}</td>
                  <td v-if="colVisible.turnover_rate">
                    {{ r.turnover_rate != null ? r.turnover_rate.toFixed(2) : '—' }}
                  </td>
                  <td v-if="colVisible.volume_ratio">
                    {{ r.volume_ratio != null ? r.volume_ratio.toFixed(2) : '—' }}
                  </td>
                  <td v-if="colVisible.total_mv" class="mono muted">{{ fmtMv(r.total_mv) }}</td>
                  <td v-if="colVisible.industry">{{ r.industry || '—' }}</td>
                  <td v-if="colVisible.trade_time" class="mono muted">{{ fmtTime(r.trade_time) }}</td>
                  <td v-if="colVisible.amplitude">{{ fmtNum(r.amplitude, 2) }}</td>
                  <td>{{ fmtAmount(r.amount) }}</td>
                  <td class="ops">
                    <div class="row-ops">
                      <button type="button" class="icon-btn" title="K线" @click="openChart(r)">
                        <svg
                          viewBox="0 0 24 24"
                          fill="none"
                          stroke="currentColor"
                          stroke-width="1.6"
                          stroke-linecap="round"
                          stroke-linejoin="round"
                        >
                          <path
                            d="M5 4v2.5M5 17.5V20M5 6.5a1.5 1.5 0 011.5-1.5h0A1.5 1.5 0 018 6.5v11a1.5 1.5 0 01-1.5 1.5h0A1.5 1.5 0 015 17.5v-11z"
                          />
                          <path
                            d="M12 2v4M12 18v4M12 6a1.5 1.5 0 011.5-1.5h0A1.5 1.5 0 0115 6v12a1.5 1.5 0 01-1.5 1.5h0A1.5 1.5 0 0112 18V6z"
                          />
                          <path
                            d="M19 6v3M19 17v4M19 9a1.5 1.5 0 011.5-1.5h0a1.5 1.5 0 011.5 1.5v8a1.5 1.5 0 01-1.5 1.5h0a1.5 1.5 0 01-1.5-1.5V9z"
                          />
                        </svg>
                      </button>
                      <button
                        type="button"
                        class="icon-btn"
                        :class="{ on: watchSet.has(r.vt_symbol) }"
                        :title="watchSet.has(r.vt_symbol) ? '在自选，点击移除' : '加自选'"
                        @click="toggleWatch(r)"
                      >
                        <svg
                          viewBox="0 0 24 24"
                          fill="none"
                          stroke="currentColor"
                          stroke-width="1.6"
                          stroke-linecap="round"
                          stroke-linejoin="round"
                        >
                          <path
                            d="M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.69h4.915c.969 0 1.371 1.24.588 1.81l-3.976 2.888a1 1 0 00-.363 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.976-2.888a1 1 0 00-1.176 0l-3.976 2.888c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 00-.363-1.118l-3.976-2.888c-.784-.57-.38-1.81.588-1.81h4.914a1 1 0 00.951-.69l1.519-4.674z"
                          />
                        </svg>
                      </button>
                      <button type="button" class="icon-btn" title="基本面" @click="openFund(r)">
                        <svg
                          viewBox="0 0 24 24"
                          fill="none"
                          stroke="currentColor"
                          stroke-width="1.6"
                          stroke-linecap="round"
                          stroke-linejoin="round"
                        >
                          <path
                            d="M3 3h18v18H3V3zM7 7h10M7 11h10M7 15h6"
                          />
                        </svg>
                      </button>
                      <button
                        type="button"
                        class="icon-btn"
                        title="分析"
                        @click.stop="analysis.open(r.vt_symbol, r.name)"
                      >
                        <svg
                          viewBox="0 0 24 24"
                          fill="none"
                          stroke="currentColor"
                          stroke-width="1.6"
                          stroke-linecap="round"
                          stroke-linejoin="round"
                        >
                          <path
                            d="M8.25 21v-4.875c0-.621.504-1.125 1.125-1.125h5.25c.621 0 1.125.504 1.125 1.125V21m0 0h4.5M3.75 21h4.5M3.75 21V9m0 0l-1.5 3M3.75 9l9-6 9 6m-13.5 0v6h4.5v-6"
                          />
                        </svg>
                      </button>
                    </div>
                  </td>
                </tr>
              </template>
              <tr v-if="useVirtual && virtualWindow.padBottom" class="vpad">
                <td :colspan="emptyColspan" :style="{ height: virtualWindow.padBottom + 'px' }"></td>
              </tr>
              <tr v-if="!ranks.length">
                <td :colspan="emptyColspan" class="empty">
                  暂无排行（需 Redis 行情快照）
                  <RouterLink to="/ops" class="draft-link">去 Ops</RouterLink>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <Teleport to="body">
      <div v-if="chartVt" class="chart-overlay" @click.self="closeChart">
        <div class="chart-modal" role="dialog" aria-modal="true" aria-label="K线图">
          <div class="chart-modal-head">
            <strong>{{ chartRow?.name || chartVt }}</strong>
            <span class="mono muted">{{ chartVt }}</span>
            <div class="spacer"></div>
            <button type="button" class="icon-btn" title="关闭" @click="closeChart">
              <svg
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="2"
                stroke-linecap="round"
                stroke-linejoin="round"
              >
                <path d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
          <div class="bar-controls">
            <div class="limits">
              <button
                type="button"
                class="chip"
                :class="{ on: barInterval === 'd' }"
                @click="barInterval = 'd'"
              >
                日K
              </button>
              <button
                type="button"
                class="chip"
                :class="{ on: barInterval === '1m' }"
                @click="barInterval = '1m'"
              >
                1分
              </button>
            </div>
            <div class="limits">
              <button
                v-for="n in barLimitChoices"
                :key="n"
                type="button"
                class="chip"
                :class="{ on: barLimit === n }"
                @click="barLimit = n"
              >
                {{ barInterval === '1m' ? `${n}根` : `${n}日` }}
              </button>
            </div>
          </div>
          <p v-if="chartBarsLoading" class="muted">
            {{ barInterval === '1m' ? '加载 1 分 K…' : '加载日 K…' }}
          </p>
          <template v-else-if="chartBarsError">
            <p class="err">
              {{ chartBarsError }}
              <RouterLink to="/ops" class="draft-link">{{
                barInterval === '1m' ? '去 Ops 补全 1 分 K' : '去 Ops 补全日 K'
              }}</RouterLink>
            </p>
          </template>
          <template v-else-if="!chartBars.length">
            <p class="muted">
              {{ barInterval === '1m' ? '暂无 1 分 K' : '暂无日 K' }}
              <RouterLink to="/ops" class="draft-link">{{
                barInterval === '1m' ? '去 Ops 补全 1 分 K' : '去 Ops 补全日 K'
              }}</RouterLink>
            </p>
          </template>
          <div v-else class="chart">
            <CandleChart :bars="chartBars" :height="400" :interval="barInterval" />
          </div>
        </div>
      </div>
    </Teleport>

    <Teleport to="body">
      <div v-if="fundVt" class="chart-overlay" @click.self="closeFund">
        <div class="chart-modal fund-modal" role="dialog" aria-modal="true" aria-label="基本面">
          <div class="chart-modal-head">
            <strong>{{ fundRow?.name || fundVt }}</strong>
            <span class="mono muted">{{ fundVt }}</span>
            <div class="spacer"></div>
            <button type="button" class="icon-btn" title="关闭" @click="closeFund">
              <svg
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="2"
                stroke-linecap="round"
                stroke-linejoin="round"
              >
                <path d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
          <p v-if="fundLoading" class="muted">加载基本面…</p>
          <p v-else-if="fundError" class="err">{{ fundError }}</p>
          <template v-else-if="fundData">
            <div class="fund-block">
              <h4>财报</h4>
              <template v-if="fundData.snapshot">
                <p class="muted">
                  期末 {{ fmtYmd(fundData.snapshot.end_date) }}
                  <span v-if="fundData.sync?.last_sync_at">
                    · 同步 {{ fundData.sync.last_sync_at }}</span
                  >
                </p>
                <dl class="fund-grid">
                  <div>
                    <dt>营收</dt>
                    <dd class="mono">{{ fmtMoney(fundData.snapshot.revenue) }}</dd>
                  </div>
                  <div>
                    <dt>净利</dt>
                    <dd class="mono">{{ fmtMoney(fundData.snapshot.net_income) }}</dd>
                  </div>
                  <div>
                    <dt>营收同比</dt>
                    <dd>{{ fmtRatioPct(fundData.snapshot.revenue_yoy) }}</dd>
                  </div>
                  <div>
                    <dt>净利同比</dt>
                    <dd>{{ fmtRatioPct(fundData.snapshot.net_income_yoy) }}</dd>
                  </div>
                  <div>
                    <dt>ROE</dt>
                    <dd>{{ fmtRatioPct(fundData.snapshot.roe) }}</dd>
                  </div>
                  <div>
                    <dt>资产负债率</dt>
                    <dd>{{ fmtRatioPct(fundData.snapshot.debt_ratio) }}</dd>
                  </div>
                </dl>
              </template>
              <p v-else class="muted">
                暂无财报
                <RouterLink to="/ops" class="draft-link">去 Ops 同步自选财报</RouterLink>
              </p>
            </div>
            <div class="fund-block">
              <h4>披露</h4>
              <template v-if="fundData.disclosures.length">
                <table class="fund-disc">
                  <thead>
                    <tr>
                      <th>报告期</th>
                      <th>预告</th>
                      <th>公告</th>
                      <th>实际</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="d in fundData.disclosures" :key="d.end_date">
                      <td class="mono">{{ fmtYmd(d.end_date) }}</td>
                      <td class="mono">{{ fmtYmd(d.pre_date) }}</td>
                      <td class="mono">{{ fmtYmd(d.ann_date) }}</td>
                      <td class="mono">{{ fmtYmd(d.actual_date) }}</td>
                    </tr>
                  </tbody>
                </table>
              </template>
              <p v-else class="muted">
                暂无披露日历
                <RouterLink to="/ops" class="draft-link">去 Ops 同步披露计划</RouterLink>
              </p>
            </div>
          </template>
          <p v-else class="muted">无基本面数据</p>
        </div>
      </div>
    </Teleport>
  </AppShell>
  <StockAnalysisModal />
</template>

<style scoped>
.page {
  display: grid;
  gap: 14px;
}
.cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 10px;
}
.card {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: 0.75rem;
  box-shadow: var(--shadow-card);
  padding: 14px 16px;
  display: grid;
  gap: 2px;
  align-content: start;
}
.card.cycle-card {
  position: relative;
  border-color: var(--brand-soft);
  background: linear-gradient(180deg, #fffdfb 0%, var(--surface) 100%);
}
.card.cycle-card::before {
  content: '';
  position: absolute;
  left: 0;
  top: 14px;
  bottom: 14px;
  width: 3px;
  border-radius: 999px;
  background: linear-gradient(180deg, var(--brand), #f5936a);
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
.status-line {
  display: flex;
  align-items: center;
  gap: 8px;
}
.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}
.dot.ok {
  background: var(--ok);
  box-shadow: 0 0 0 3px rgba(22, 163, 74, 0.15);
}
.dot.warn {
  background: var(--danger);
  box-shadow: 0 0 0 3px rgba(225, 29, 72, 0.15);
}
.trading-badge {
  margin-left: 2px;
  font-size: 0.72rem;
  font-weight: 600;
  padding: 1px 8px;
  border-radius: 999px;
  line-height: 1.5;
  white-space: nowrap;
}
.trading-badge.on {
  color: #fff;
  background: var(--ok);
}
.trading-badge.off {
  color: var(--ink-muted);
  background: var(--surface-muted);
  border: 1px solid var(--line-soft);
}
.s {
  margin-top: 4px;
  font-size: 0.8rem;
}
.cycle-head {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 8px;
  margin-top: 4px;
}
.cycle-head .v {
  margin-top: 0;
}
.cycle-gate {
  font-size: 0.8rem;
  font-weight: 600;
  padding: 3px 10px;
  border-radius: 999px;
  border: 1px solid var(--border);
}
.cycle-gate.ok {
  color: #fff;
  background: var(--ok);
  border-color: var(--ok);
}
.cycle-gate.warn {
  color: #fff;
  background: var(--danger);
  border-color: var(--danger);
}
.cycle-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 8px;
}
.draft-link {
  color: var(--brand);
  margin-left: 4px;
}
.cross-link {
  color: var(--brand);
  text-decoration: none;
  font-size: 0.85rem;
  white-space: nowrap;
}
.cross-link:hover {
  text-decoration: underline;
}
.empty-cycle-hint {
  margin: 6px 0 0;
}
.warn {
  color: var(--danger);
}
.toolbar {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
  flex-wrap: wrap;
}
.tabs,
.actions {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  align-items: center;
}
.tabs button {
  background: var(--surface);
  border: 1px solid var(--line);
  color: var(--ink-muted);
  border-radius: 0.5rem;
  padding: 7px 12px;
  font-size: 0.8125rem;
  transition:
    background 0.15s ease,
    color 0.15s ease,
    border-color 0.15s ease;
}
.tabs button:hover {
  color: var(--ink);
  border-color: var(--brand-soft);
}
.tabs button.on {
  background: var(--brand-light);
  color: var(--brand);
  border-color: var(--brand-soft);
  font-weight: 500;
}
.auto {
  display: flex;
  gap: 6px;
  align-items: center;
  color: var(--muted);
  font-size: 0.8rem;
}
.ghost,
.primary {
  border-radius: 0.5rem;
  padding: 6px 10px;
  border: 1px solid var(--border);
  cursor: pointer;
}
.ghost {
  background: transparent;
  color: var(--text);
}
.ghost.on {
  border-color: var(--brand, #333);
  color: var(--text);
  font-weight: 500;
}
.filter-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}
.board-filter {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
}
.count-hint {
  font-size: 0.8rem;
  font-variant-numeric: tabular-nums;
}
.search-all-tag {
  margin-left: 6px;
  font-size: 0.72rem;
  color: var(--brand);
  background: var(--brand-light);
  border: 1px solid var(--brand-soft);
  border-radius: 999px;
  padding: 1px 8px;
  font-variant-numeric: normal;
}
.filter-row input {
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: 0.5rem;
  color: var(--text);
  padding: 6px 10px;
  min-width: 160px;
}
.empty-hint {
  margin: 0;
  padding: 12px;
}
.primary {
  background: var(--accent);
  border-color: transparent;
  color: var(--brand-foreground);
  font-weight: 600;
}
.err {
  margin: 0;
  color: var(--danger);
  font-size: 0.85rem;
}
.muted {
  color: var(--muted);
}
.split {
  display: grid;
  gap: 12px;
  min-height: 420px;
}
.table-wrap {
  border: 1px solid var(--line);
  border-radius: 0.75rem;
  background: var(--surface);
  box-shadow: var(--shadow-card);
  overflow: auto;
  max-height: 70vh;
}
.bar-controls {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}
.limits {
  display: flex;
  gap: 4px;
}
.chip {
  background: transparent;
  border: 1px solid var(--border);
  color: var(--muted);
  border-radius: 0.5rem;
  padding: 4px 8px;
  font-size: 0.75rem;
  cursor: pointer;
}
.chip:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}
.chip.on {
  background: var(--brand-light);
  color: var(--brand);
  border-color: var(--brand-soft);
  font-weight: 500;
}
.link {
  background: none;
  border: none;
  padding: 2px 4px;
  color: var(--muted);
  cursor: pointer;
  font-size: 0.8rem;
  white-space: nowrap;
}
.link:hover {
  color: var(--brand);
}
.icon-btn {
  display: inline-grid;
  place-items: center;
  width: 26px;
  height: 24px;
  padding: 0;
  border: 1px solid var(--line);
  border-radius: 0.4rem;
  background: transparent;
  color: var(--ink-muted);
  cursor: pointer;
}
.icon-btn:hover {
  background: var(--surface-muted);
  border-color: var(--brand);
  color: var(--brand);
}
.icon-btn svg {
  width: 15px;
  height: 15px;
}
.icon-btn.on {
  color: var(--brand);
  border-color: var(--brand-soft);
  background: var(--brand-light);
}
.row-ops {
  display: flex;
  gap: 4px;
}
th.ops,
td.ops {
  text-align: right;
}
.fund-modal {
  max-width: 560px;
}
.fund-block {
  display: grid;
  gap: 6px;
}
.fund-block h4 {
  margin: 0;
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--ink);
}
.fund-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 6px 16px;
  margin: 0;
}
.fund-grid dt {
  color: var(--muted);
  font-size: 0.75rem;
}
.fund-grid dd {
  margin: 0;
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--ink);
}
.fund-disc {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.8rem;
}
.fund-disc th,
.fund-disc td {
  padding: 5px 8px;
  border-bottom: 1px solid var(--line-soft);
  text-align: left;
}
.fund-disc th {
  color: var(--muted);
  font-weight: 500;
  background: var(--surface-muted);
}
.chart-overlay {
  position: fixed;
  inset: 0;
  z-index: 1000;
  display: grid;
  place-items: center;
  background: rgba(0, 0, 0, 0.45);
  padding: 24px;
}
.chart-modal {
  width: 100%;
  max-width: 860px;
  max-height: 88vh;
  display: grid;
  gap: 12px;
  padding: 16px 18px;
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: 0.875rem;
  box-shadow: var(--shadow-panel);
}
.chart-modal-head {
  display: flex;
  align-items: baseline;
  gap: 8px;
}
.chart-modal-head strong {
  font-size: 1rem;
}
.chart-modal-head .mono {
  font-size: 0.78rem;
}
.chart-modal-head .spacer {
  flex: 1;
}
.chart-modal :deep(.candle svg) {
  height: 400px;
}
.chart {
  border-top: 1px solid var(--border);
  padding-top: 8px;
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
  position: sticky;
  top: 0;
  font-weight: 500;
}
th.sortable {
  cursor: pointer;
  user-select: none;
}
tbody tr:hover td {
  background: var(--surface-muted);
}
/* 虚拟滚动占位行：透明、无边框、不触发 hover */
tbody tr.vpad td {
  padding: 0;
  border-bottom: 0;
  background: transparent !important;
}
tbody tr.vpad {
  pointer-events: none;
}
.rank-badge {
  display: inline-grid;
  place-items: center;
  min-width: 24px;
  height: 20px;
  border-radius: 999px;
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--ink-muted);
  font-variant-numeric: tabular-nums;
}
.rank-badge.rank-1 {
  background: #fde8d7;
  color: #b45309;
}
.rank-badge.rank-2 {
  background: #eef0f3;
  color: #52525b;
}
.rank-badge.rank-3 {
  background: #fbe3dc;
  color: #9a5b3f;
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
.thresholds-section {
  border: 1px solid var(--border);
  border-radius: 0.75rem;
  background: var(--bg-elevated);
  padding: 12px 14px;
}
.thresholds-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
}
.thresholds-head strong {
  margin-right: 8px;
}
.tag {
  font-size: 0.78rem;
}
.tiny-btn {
  padding: 4px 8px;
  font-size: 0.8rem;
}
.thresholds-panel {
  margin-top: 10px;
  display: grid;
  gap: 10px;
}
.thresholds-hint {
  margin: 0;
  font-size: 0.78rem;
}
.thresholds-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 8px 12px;
}
.threshold-row {
  display: grid;
  gap: 4px;
}
.threshold-row label {
  font-size: 0.78rem;
  color: var(--muted);
}
.threshold-row input[type='number'] {
  width: 100%;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: var(--bg);
  color: var(--text);
  padding: 6px 8px;
  font-size: 0.85rem;
}
.thresholds-actions {
  display: flex;
  gap: 8px;
}
.ok {
  margin: 0;
  color: var(--ok);
  font-size: 0.85rem;
}
</style>

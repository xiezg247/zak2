<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import AppShell from '../components/AppShell.vue'
import CandleChart from '../components/CandleChart.vue'
import { marketApi, type EmotionThresholds, type MarketOverview, type RankRow } from '../api/market'
import { watchlistApi, type Bar } from '../api/watchlist'
import { POLL_FAST_MS, POLL_SLOW_MS, useQuoteNotify } from '../composables/useQuoteNotify'

const router = useRouter()
const overview = ref<MarketOverview | null>(null)
const field = ref('change_pct')
const ranks = ref<RankRow[]>([])
const error = ref('')
const loading = ref(false)
const autoRefresh = ref(true)
const selected = ref<RankRow | null>(null)
const bars = ref<Bar[]>([])
const barsError = ref('')
const barsLoading = ref(false)
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
const addMsg = ref('')
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

function restartPoll() {
  if (timer) window.clearInterval(timer)
  const ms = connected.value ? POLL_SLOW_MS : POLL_FAST_MS
  timer = window.setInterval(tick, ms)
}

watch(connected, () => restartPoll())

const fields = [
  { id: 'change_pct', label: '涨幅', col: '涨幅%' },
  { id: 'turnover_rate', label: '换手', col: '换手%' },
  { id: 'amount', label: '成交额', col: '成交额' },
  { id: 'volume_ratio', label: '量比', col: '量比' },
  { id: 'limit_times', label: '连板', col: '连板' },
]

const fieldMeta = computed(() => fields.find((f) => f.id === field.value) || fields[0])

type SortKey =
  'last_price' | 'change_pct' | 'turnover_rate' | 'amount' | 'volume_ratio' | 'limit_times' | null

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
  if (id === 'turnover_rate' || id === 'amount' || id === 'volume_ratio' || id === 'limit_times') {
    return id
  }
  return null
})

const displayedRanks = computed(() => {
  const q = listFilter.value.trim().toLowerCase()
  let list = ranks.value
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

const subtitle = computed(() => {
  const o = overview.value
  if (!o) return ''
  const cycle = o.emotion_cycle
  if (cycle?.stage_label) {
    const gate = cycle.allow_new_positions ? '可新开' : '不宜新开'
    return `行情 ${o.quote_count} · ${cycle.stage_label} · ${gate}`
  }
  const emo = o.emotion
  const emoText = emo ? `最高板 ${emo.max_limit_times} · ${emo.max_board_vt_symbol}` : '无情绪梯队'
  return `行情 ${o.quote_count} · ${emoText}`
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
  if (id === 'limit_times') return r.limit_times != null ? String(r.limit_times) : '—'
  return r.score.toFixed(2)
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
      ranks.value = await marketApi.ranks(field.value, 50)
      if (selected.value) {
        selected.value =
          ranks.value.find((r) => r.vt_symbol === selected.value?.vt_symbol) || selected.value
      }
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
  selected.value = null
  bars.value = []
  barsError.value = ''
  barsLoading.value = false
  try {
    ranks.value = await marketApi.ranks(field.value, 50)
  } catch (e) {
    ranks.value = []
    error.value = e instanceof Error ? e.message : '排行加载失败'
  }
}

async function loadBars() {
  barsError.value = ''
  bars.value = []
  if (!selected.value) {
    barsLoading.value = false
    return
  }
  barsLoading.value = true
  try {
    const resp = await watchlistApi.bars(
      selected.value.vt_symbol,
      barInterval.value,
      barLimit.value,
    )
    bars.value = resp.bars
  } catch (e) {
    barsError.value = e instanceof Error ? e.message : '无 K 线'
  } finally {
    barsLoading.value = false
  }
}

async function selectRank(r: RankRow) {
  selected.value = r
  addMsg.value = ''
  await loadBars()
}

async function addSelected() {
  if (!selected.value) return
  addMsg.value = ''
  try {
    await watchlistApi.add(selected.value.vt_symbol, selected.value.name || '')
    addMsg.value = '已加入自选'
  } catch (e) {
    addMsg.value = e instanceof Error ? e.message : '加入失败'
  }
}

function openInWatchlist() {
  if (!selected.value) return
  void router.push({ path: '/watchlist', query: { symbol: selected.value.vt_symbol } })
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
  if (selected.value) void loadBars()
})

onMounted(() => {
  void load()
  restartPoll()
})

onUnmounted(() => {
  if (timer) window.clearInterval(timer)
})
</script>

<template>
  <AppShell title="市场" :subtitle="subtitle" active="market">
    <div class="page">
      <section class="cards" v-if="overview">
        <div class="card">
          <div class="k">Redis</div>
          <div class="v status-line">
            <span class="dot" :class="overview.redis_available ? 'ok' : 'warn'"></span>
            {{ overview.redis_available ? '在线' : '离线' }} · {{ overview.quote_count }} 只
          </div>
          <div class="s muted">{{ overview.updated_at || '—' }}</div>
        </div>
        <div class="card cycle-card" v-if="overview.emotion_cycle">
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
          <div class="s warn" v-for="(w, i) in overview.emotion_cycle.warnings" :key="i">
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
          <div class="s muted" v-if="cycleInputsOpen && overview.emotion_cycle.inputs">
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
        <div class="card" v-else>
          <div class="k">情绪周期</div>
          <div class="v muted">暂无数据</div>
          <p class="s muted empty-cycle-hint">
            可到 Ops 执行 warm_market_summary 预热。
            <RouterLink to="/ops" class="draft-link">去 Ops</RouterLink>
          </p>
        </div>
        <div class="card" v-if="overview.emotion">
          <div class="k">连板情绪</div>
          <div class="v">最高 {{ overview.emotion.max_limit_times }} 板</div>
          <div class="s muted">
            {{ overview.emotion.trade_date }} · {{ overview.emotion.max_board_vt_symbol }} · 关联
            {{ overview.emotion.linked_board_count }}
          </div>
        </div>
        <div class="card" v-else>
          <div class="k">连板情绪</div>
          <div class="v muted">暂无数据</div>
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
            {{ connected ? 'WS+慢轮询' : '15s 刷新' }}
          </label>
          <button class="ghost" type="button" :disabled="loading" @click="load()">刷新</button>
          <RouterLink to="/sectors" class="cross-link">板块资金 →</RouterLink>
        </div>
      </div>

      <p v-if="error" class="err">{{ error }}</p>

      <div v-if="ranks.length" class="filter-row">
        <input v-model="listFilter" placeholder="过滤代码/名称" />
        <button type="button" class="ghost" :class="{ on: !sortKey }" @click="clearSort">
          默认序
        </button>
      </div>

      <div class="split">
        <div class="table-wrap">
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
                <th class="sortable" @click="toggleSort('change_pct')">
                  涨幅%{{ sortMark('change_pct') }}
                </th>
                <th v-if="scoreSortKey" class="sortable" @click="toggleSort(scoreSortKey)">
                  {{ fieldMeta.col }}{{ sortMark(scoreSortKey) }}
                </th>
                <th v-else>{{ fieldMeta.col }}</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="(r, i) in displayedRanks"
                :key="r.tf_symbol"
                :class="{ on: selected?.vt_symbol === r.vt_symbol }"
                @click="selectRank(r)"
              >
                <td>
                  <span class="rank-badge" :class="'rank-' + (i + 1)">{{ i + 1 }}</span>
                </td>
                <td class="mono">{{ r.vt_symbol }}</td>
                <td>{{ r.name || '—' }}</td>
                <td>{{ r.last_price != null ? r.last_price.toFixed(2) : '—' }}</td>
                <td :class="{ up: (r.change_pct || 0) > 0, down: (r.change_pct || 0) < 0 }">
                  {{ r.change_pct != null ? r.change_pct.toFixed(2) : '—' }}
                </td>
                <td>{{ scoreLabel(r) }}</td>
              </tr>
              <tr v-if="!ranks.length">
                <td colspan="6" class="empty">
                  暂无排行（需 Redis 行情快照）
                  <RouterLink to="/ops" class="draft-link">去 Ops</RouterLink>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <aside class="detail" v-if="selected">
          <div class="detail-head">
            <div class="detail-id">
              <strong>{{ selected.name || selected.vt_symbol }}</strong>
              <div class="mono muted">{{ selected.vt_symbol }}</div>
            </div>
            <div
              class="detail-price"
              :class="{
                up: (selected.change_pct || 0) > 0,
                down: (selected.change_pct || 0) < 0,
              }"
            >
              <span class="price mono">{{
                selected.last_price != null ? selected.last_price.toFixed(2) : '—'
              }}</span>
              <span class="change mono">
                {{
                  selected.change_pct != null
                    ? (selected.change_pct > 0 ? '+' : '') + selected.change_pct.toFixed(2) + '%'
                    : '—'
                }}
              </span>
            </div>
          </div>
          <div class="detail-actions">
            <button type="button" class="primary" @click="addSelected">加自选</button>
            <button type="button" class="ghost" @click="openInWatchlist">在自选打开</button>
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
          <p v-if="addMsg" class="muted">{{ addMsg }}</p>
          <p v-if="barsLoading" class="muted">
            {{ barInterval === '1m' ? '加载 1 分 K…' : '加载日 K…' }}
          </p>
          <template v-else-if="barsError">
            <p class="err">
              {{ barsError }}
              <RouterLink to="/ops" class="draft-link">{{
                barInterval === '1m' ? '去 Ops 补全 1 分 K' : '去 Ops 补全日 K'
              }}</RouterLink>
            </p>
          </template>
          <template v-else-if="!bars.length">
            <p class="muted">
              {{ barInterval === '1m' ? '暂无 1 分 K' : '暂无日 K' }}
              <RouterLink to="/ops" class="draft-link">{{
                barInterval === '1m' ? '去 Ops 补全 1 分 K' : '去 Ops 补全日 K'
              }}</RouterLink>
            </p>
          </template>
          <div v-else class="chart">
            <CandleChart :bars="bars" :height="240" :interval="barInterval" />
          </div>
        </aside>
        <aside v-else class="detail empty-panel muted">点击排行行查看 K 线与操作</aside>
      </div>
    </div>
  </AppShell>
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
  grid-template-columns: 1.2fr 0.9fr;
  gap: 12px;
  min-height: 420px;
}
.table-wrap,
.detail {
  border: 1px solid var(--line);
  border-radius: 0.75rem;
  background: var(--surface);
  box-shadow: var(--shadow-card);
}
.table-wrap {
  overflow: auto;
  max-height: 70vh;
}
.detail {
  padding: 14px;
  display: grid;
  gap: 10px;
  align-content: start;
}
.empty-panel {
  place-content: center;
  text-align: center;
  min-height: 240px;
}
.detail-head {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  align-items: flex-start;
  padding-bottom: 10px;
  border-bottom: 1px solid var(--line-soft);
}
.detail-id {
  display: grid;
  gap: 2px;
  min-width: 0;
}
.detail-id strong {
  font-size: 0.95rem;
  font-weight: 600;
}
.detail-id .mono {
  font-size: 0.75rem;
}
.detail-price {
  display: flex;
  align-items: baseline;
  gap: 8px;
  white-space: nowrap;
}
.detail-price .price {
  font-size: 1.35rem;
  font-weight: 700;
  line-height: 1;
  font-variant-numeric: tabular-nums;
}
.detail-price .change {
  font-size: 0.82rem;
  font-weight: 600;
}
.detail-price.up {
  color: var(--danger);
}
.detail-price.down {
  color: var(--ok);
}
.detail-actions {
  display: flex;
  gap: 8px;
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
.chip.on {
  background: var(--brand-light);
  color: var(--brand);
  border-color: var(--brand-soft);
  font-weight: 500;
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
tbody tr {
  cursor: pointer;
}
tbody tr:hover td {
  background: var(--surface-muted);
}
tbody tr.on td {
  background: var(--brand-light);
}
tbody tr.on:hover td {
  background: var(--brand-light);
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
@media (max-width: 960px) {
  .split {
    grid-template-columns: 1fr;
  }
}
</style>

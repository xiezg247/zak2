<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import AppShell from '../components/AppShell.vue'
import StockAnalysisModal from '../components/StockAnalysisModal.vue'
import {
  marketApi,
  type RadarCard,
  type RadarHorizon,
  type RadarPredict,
  type RadarResonanceEntry,
  type ResonanceWeightItem,
} from '../api/market'
import { watchlistApi } from '../api/watchlist'
import { useStockAnalysis } from '../composables/useStockAnalysis'

const analysis = useStockAnalysis()

const router = useRouter()
const cards = ref<RadarCard[]>([])
const resonance = ref<RadarResonanceEntry[]>([])
const resonanceFilter = ref('')

const displayedResonance = computed(() => {
  const q = resonanceFilter.value.trim().toLowerCase()
  if (!q) return resonance.value
  return resonance.value.filter((e) => {
    const vt = (e.vt_symbol || '').toLowerCase()
    const name = (e.name || '').toLowerCase()
    return vt.includes(q) || name.includes(q)
  })
})

const activeId = ref('')
const error = ref('')
const loading = ref(false)
const sideOpen = ref(true)
const sideMsg = ref('')
const detailMsg = ref('')
const rowActionMsg = ref('')
const actingVt = ref('')
const weightOpen = ref(false)
const weightItems = ref<ResonanceWeightItem[]>([])
const weightDraft = ref<Record<string, number>>({})
const weightBusy = ref(false)
const weightErr = ref('')
const horizon = ref<RadarHorizon | null>(null)
const horizonErr = ref('')
const horizonOpen = ref(false)
const predict = ref<RadarPredict | null>(null)
const predictErr = ref('')
const predictOpen = ref(false)

const cardFilter = ref('')
const sourceChip = ref('')
const cardSortKey = ref<'title' | 'rows' | null>(null)
const cardSortDir = ref<'asc' | 'desc'>('desc')

const SOURCE_LABELS: Record<string, string> = {
  cache: '缓存',
  synthesized: '合成',
}

function sourceLabel(source: string): string {
  return SOURCE_LABELS[source] || source
}

const sourceOptions = computed(() => {
  const set = new Set<string>()
  for (const c of cards.value) {
    const s = (c.source || '').trim()
    if (s) set.add(s)
  }
  return [...set].sort((a, b) => a.localeCompare(b, 'zh'))
})

function cmpCardNullable(
  a: number | string | null | undefined,
  b: number | string | null | undefined,
  dir: 'asc' | 'desc',
): number {
  const aM = a == null || a === '' || (typeof a === 'number' && Number.isNaN(a))
  const bM = b == null || b === '' || (typeof b === 'number' && Number.isNaN(b))
  if (aM && bM) return 0
  if (aM) return 1
  if (bM) return -1
  if (typeof a === 'number' && typeof b === 'number') {
    const d = a - b
    return dir === 'asc' ? d : -d
  }
  const d = String(a).localeCompare(String(b), 'zh')
  return dir === 'asc' ? d : -d
}

function toggleCardSort(key: 'title' | 'rows') {
  if (cardSortKey.value === key) {
    cardSortDir.value = cardSortDir.value === 'asc' ? 'desc' : 'asc'
  } else {
    cardSortKey.value = key
    cardSortDir.value = 'desc'
  }
}

function clearCardSort() {
  cardSortKey.value = null
}

function cardSortMark(key: 'title' | 'rows'): string {
  if (cardSortKey.value !== key) return ''
  return cardSortDir.value === 'asc' ? ' ▲' : ' ▼'
}

const displayedCards = computed(() => {
  const q = cardFilter.value.trim().toLowerCase()
  let list = cards.value
  if (sourceChip.value) {
    list = list.filter((c) => (c.source || '').trim() === sourceChip.value)
  }
  if (q) {
    list = list.filter((c) => {
      const t = (c.title || '').toLowerCase()
      const sub = (c.subtitle || '').toLowerCase()
      const src = (c.source || '').toLowerCase()
      return t.includes(q) || sub.includes(q) || src.includes(q)
    })
  }
  const key = cardSortKey.value
  if (!key) return list
  const dir = cardSortDir.value
  return [...list].sort((a, b) => {
    if (key === 'rows') return cmpCardNullable(a.rows.length, b.rows.length, dir)
    return cmpCardNullable(a.title || '', b.title || '', dir)
  })
})

const active = computed(() => {
  if (!activeId.value) return null
  return cards.value.find((c) => c.card_id === activeId.value) || null
})

watch(displayedCards, (list) => {
  if (!list.length) {
    if (cards.value.length) activeId.value = ''
    return
  }
  if (!list.some((c) => c.card_id === activeId.value)) {
    activeId.value = list[0].card_id
  }
})

watch(activeId, () => {
  detailMsg.value = ''
})

const subtitle = computed(() => {
  if (!cards.value.length) return ''
  const n = resonance.value.length
  return n ? `${cards.value.length} 张卡片 · 共振 ${n}` : `${cards.value.length} 张卡片`
})

const horizonHasCache = computed(() => Boolean(horizon.value?.computed_at))

const horizonHeadLabel = computed(() => {
  if (!horizonHasCache.value) return '暂无数据'
  const h = horizon.value!
  return (h.label || '').trim() || '启发式展望（基于共振）'
})

const horizonSummary = computed(() => {
  if (!horizonHasCache.value) return '暂无数据'
  const h = horizon.value!
  if (h.empty) return `扫描 ${h.scanned_total} · 无入选`
  return `入选 ${h.rows.length} · 扫描 ${h.scanned_total}`
})

const predictHasCache = computed(() => Boolean(predict.value?.computed_at))

const predictHeadLabel = computed(() => {
  if (!predictHasCache.value) return '暂无数据'
  const p = predict.value!
  return (p.label || '').trim() || '规则预测（共振+可解释加分）'
})

const predictSummary = computed(() => {
  if (!predictHasCache.value) return '暂无数据'
  const p = predict.value!
  if (p.empty) return `扫描 ${p.scanned_total} · 无入选`
  return `入选 ${p.rows.length} · 扫描 ${p.scanned_total}`
})

const cardCountByVt = computed(() => {
  const m = new Map<string, number>()
  for (const e of resonance.value) {
    m.set(e.vt_symbol, e.card_count)
    const s = e.vt_symbol
    if (s.includes('.')) {
      const [a, b] = s.split('.')
      if (b === 'SSE') m.set(`SHSE.${a}`, e.card_count)
      else if (b === 'SZSE') m.set(`SZSE.${a}`, e.card_count)
      else if (b === 'BSE') m.set(`BJSE.${a}`, e.card_count)
      else if (a === 'SHSE' || a === 'SZSE' || a === 'BJSE')
        m.set(`${b}.${a === 'SHSE' ? 'SSE' : a === 'BJSE' ? 'BSE' : 'SZSE'}`, e.card_count)
    }
  }
  return m
})

function applyWeights(w: { items: ResonanceWeightItem[]; weights: Record<string, number> }) {
  weightItems.value = w.items
  weightDraft.value = { ...w.weights }
}

async function loadResonance() {
  const r = await marketApi.radarResonance({ top_n: 20, min_cards: 2 })
  resonance.value = r.entries
}

async function load() {
  loading.value = true
  error.value = ''
  sideMsg.value = ''
  detailMsg.value = ''
  horizonErr.value = ''
  predictErr.value = ''
  const weightsPromise = marketApi.resonanceWeights().catch((e) => {
    weightErr.value = e instanceof Error ? e.message : '权重加载失败'
    return null
  })
  const horizonPromise = marketApi.radarHorizon().catch((e) => {
    horizonErr.value = e instanceof Error ? e.message : '展望加载失败'
    return null
  })
  const predictPromise = marketApi.radarPredict().catch((e) => {
    predictErr.value = e instanceof Error ? e.message : '预测加载失败'
    return null
  })
  try {
    const [c, r] = await Promise.all([
      marketApi.radarCards(),
      marketApi.radarResonance({ top_n: 20, min_cards: 2 }),
    ])
    cards.value = c
    resonance.value = r.entries
    if (!activeId.value && cards.value.length) activeId.value = cards.value[0].card_id
  } catch (e) {
    error.value = e instanceof Error ? e.message : '加载失败'
  } finally {
    loading.value = false
  }
  const [w, h, p] = await Promise.all([weightsPromise, horizonPromise, predictPromise])
  if (w) {
    applyWeights(w)
    weightErr.value = ''
  }
  if (h) {
    horizon.value = h
    horizonErr.value = ''
  }
  if (p) {
    predict.value = p
    predictErr.value = ''
  }
}

async function saveWeights() {
  if (weightItems.value.length === 0) {
    weightErr.value = '权重尚未加载，无法保存'
    return
  }
  const payload: Record<string, number> = {}
  for (const item of weightItems.value) {
    const v = weightDraft.value[item.card_id]
    if (typeof v === 'number' && Number.isFinite(v)) {
      payload[item.card_id] = v
    }
  }
  if (Object.keys(payload).length === 0) {
    weightErr.value = '没有可保存的权重，请先加载或填写'
    return
  }
  weightBusy.value = true
  weightErr.value = ''
  sideMsg.value = ''
  try {
    const out = await marketApi.putResonanceWeights(payload)
    applyWeights(out)
    sideMsg.value = '权重已保存'
    await loadResonance()
  } catch (e) {
    weightErr.value = e instanceof Error ? e.message : '保存失败'
  } finally {
    weightBusy.value = false
  }
}

async function resetWeights() {
  weightBusy.value = true
  weightErr.value = ''
  sideMsg.value = ''
  try {
    const out = await marketApi.putResonanceWeights({})
    applyWeights(out)
    sideMsg.value = '已恢复默认权重'
    await loadResonance()
  } catch (e) {
    weightErr.value = e instanceof Error ? e.message : '恢复失败'
  } finally {
    weightBusy.value = false
  }
}

function rowLabel(row: Record<string, unknown>) {
  return String(row.name || row.vt_symbol || row.tf_symbol || row.sector_id || '—')
}

function sealLabel(
  row: Record<string, unknown> | { seal_time_label?: string; first_time?: string },
) {
  const label = String(row.seal_time_label || '').trim()
  if (label) return label
  const ft = String((row as { first_time?: string }).first_time || '').trim()
  if (ft.length >= 4) return `${ft.slice(0, 2)}:${ft.slice(2, 4)} 封板`
  return ''
}

function rowVt(row: Record<string, unknown>): string {
  for (const k of ['vt_symbol', 'tf_symbol', 'symbol'] as const) {
    const v = String(row[k] || '').trim()
    if (v) return v
  }
  return ''
}

function rowVtKeys(row: Record<string, unknown>): string[] {
  const keys: string[] = []
  for (const k of ['vt_symbol', 'tf_symbol', 'symbol'] as const) {
    const v = String(row[k] || '').trim()
    if (v) keys.push(v)
  }
  return keys
}

function openInWatchlist(vt: string) {
  void router.push({ path: '/watchlist', query: { symbol: vt } })
}

function openInNotes(vt: string) {
  void router.push({ path: '/notes', query: { symbol: vt } })
}

function rowResonanceCount(row: Record<string, unknown>): number {
  for (const k of rowVtKeys(row)) {
    const n = cardCountByVt.value.get(k)
    if (typeof n === 'number') return n
  }
  return 0
}

function cardResonanceCount(c: RadarCard): number {
  for (const row of c.rows) {
    const n = rowResonanceCount(row)
    if (n > 0) return n
  }
  return 0
}

function goLeaderScreen() {
  void router.push({ path: '/screener', query: { recipe: 'radar_leader', variant: 'mainline' } })
}

function goResonanceScreen() {
  void router.push({ path: '/screener', query: { recipe: 'radar_resonance' } })
}

async function addWatchTo(vt: string, name: string | undefined, msg: { value: string }) {
  if (!vt || actingVt.value) return
  actingVt.value = vt
  msg.value = ''
  try {
    await watchlistApi.add(vt, name || '')
    msg.value = `已加入自选 ${vt}`
  } catch (e) {
    msg.value = e instanceof Error ? e.message : '加自选失败'
  } finally {
    actingVt.value = ''
  }
}

async function addWatch(vt: string, name?: string) {
  await addWatchTo(vt, name, sideMsg)
}

async function addWatchFromDetail(vt: string, name?: string) {
  await addWatchTo(vt, name, detailMsg)
}

async function addWatchFromHorizonRow(vt: string, name?: string) {
  await addWatchTo(vt, name, rowActionMsg)
}

onMounted(() => {
  void load()
})
</script>

<template>
  <AppShell title="雷达" :subtitle="subtitle" active="radar">
    <div class="page">
      <div class="toolbar">
        <button class="ghost" type="button" :disabled="loading" @click="load">刷新</button>
        <span v-if="loading" class="muted">加载中…</span>
        <button class="primary" type="button" @click="goLeaderScreen">龙头选股 → Hub</button>
        <button class="ghost" type="button" @click="goResonanceScreen">共振选股 → Hub</button>
        <span class="spacer"></span>
        <button class="ghost" type="button" @click="sideOpen = !sideOpen">
          {{ sideOpen ? '收起共振榜' : '展开共振榜' }}
        </button>
        <span v-if="active" class="muted source-hint"
          >来源 {{ sourceLabel(active.source) }} ·
          {{ active.computed_at || active.subtitle || '—' }}</span
        >
      </div>
      <p v-if="error" class="err">{{ error }}</p>
      <p v-if="rowActionMsg" class="draft-msg">{{ rowActionMsg }}</p>

      <div class="summary-bar">
        <button
          type="button"
          class="summary-card"
          :class="{ open: horizonOpen }"
          @click="horizonOpen = !horizonOpen"
        >
          <span class="summary-k">共振展望</span>
          <span class="summary-v muted">{{ horizonSummary }}</span>
          <span v-if="horizonHasCache && horizon?.computed_at" class="summary-t muted">
            {{ horizon.computed_at }}
          </span>
          <span class="chevron">{{ horizonOpen ? '▴' : '▾' }}</span>
        </button>
        <button
          type="button"
          class="summary-card"
          :class="{ open: predictOpen }"
          @click="predictOpen = !predictOpen"
        >
          <span class="summary-k">规则预测</span>
          <span class="summary-v muted">{{ predictSummary }}</span>
          <span v-if="predictHasCache && predict?.computed_at" class="summary-t muted">
            {{ predict.computed_at }}
          </span>
          <span class="chevron">{{ predictOpen ? '▴' : '▾' }}</span>
        </button>
      </div>

      <div v-if="horizonOpen" class="summary-panel">
        <div class="summary-panel-head">
          <strong>{{ horizonHeadLabel }}</strong>
          <span v-if="horizonHasCache && horizon?.computed_at" class="muted tiny">
            · {{ horizon.computed_at }}
          </span>
        </div>
        <p v-if="horizonErr" class="horizon-err">{{ horizonErr }}</p>
        <template v-else-if="horizonHasCache">
          <p v-if="horizon?.empty" class="muted">
            上次扫描无达标共振标的（扫描 {{ horizon.scanned_total }} · 入选
            {{ horizon.refined_total }}）。
          </p>
          <div v-else-if="horizon?.rows.length" class="table-wrap horizon-table">
            <table>
              <thead>
                <tr>
                  <th>#</th>
                  <th>标的</th>
                  <th>共振</th>
                  <th>卡数</th>
                  <th>细节</th>
                  <th>操作</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(row, i) in horizon.rows" :key="row.vt_symbol">
                  <td>{{ i + 1 }}</td>
                  <td>
                    <span v-if="row.card_count >= 2" class="star">★</span>
                    {{ row.name || row.vt_symbol }}
                    <div class="mono muted tiny">{{ row.vt_symbol }}</div>
                  </td>
                  <td class="mono">{{ row.resonance_score.toFixed(1) }}</td>
                  <td>{{ row.card_count }}</td>
                  <td class="mono muted">
                    <template v-if="row.change_pct != null"
                      >涨幅 {{ row.change_pct.toFixed(2) }}%</template
                    >
                    <template v-if="row.last_price != null">
                      <template v-if="row.change_pct != null"> · </template>
                      现价 {{ row.last_price.toFixed(2) }}
                    </template>
                    <template v-if="row.card_titles.length">
                      <template v-if="row.change_pct != null || row.last_price != null">
                        ·
                      </template>
                      {{ row.card_titles.join(' / ') }}
                    </template>
                    <template v-if="sealLabel(row)">
                      <template
                        v-if="
                          row.change_pct != null || row.last_price != null || row.card_titles.length
                        "
                      >
                        ·
                      </template>
                      {{ sealLabel(row) }}
                    </template>
                    <template
                      v-if="
                        row.change_pct == null &&
                        row.last_price == null &&
                        !row.card_titles.length &&
                        !sealLabel(row)
                      "
                    >
                      —
                    </template>
                  </td>
                  <td class="ops">
                    <button
                      type="button"
                      class="ghost tiny-btn"
                      @click="analysis.open(row.vt_symbol, row.name)"
                    >
                      析
                    </button>
                    <button
                      type="button"
                      class="ghost tiny-btn"
                      :disabled="!!actingVt"
                      @click="addWatchFromHorizonRow(row.vt_symbol, row.name)"
                    >
                      自选
                    </button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </template>
        <template v-else>
          <p class="muted">
            暂无启发式展望数据。请于 Ops 手动执行
            <code class="mono">scan_horizon_outlook</code>（需先 warm_radar_card_snapshots）。
          </p>
          <RouterLink to="/ops" class="draft-link">去 Ops</RouterLink>
        </template>
      </div>

      <div v-if="predictOpen" class="summary-panel">
        <div class="summary-panel-head">
          <strong>{{ predictHeadLabel }}</strong>
          <span v-if="predictHasCache && predict?.computed_at" class="muted tiny">
            · {{ predict.computed_at }}
          </span>
        </div>
        <p v-if="predictErr" class="horizon-err">{{ predictErr }}</p>
        <template v-else-if="predictHasCache">
          <p v-if="predict?.empty" class="muted">
            上次预测无入选行（候选 {{ predict.scanned_total }} · 缺日 K
            {{ predict.kline_missing }}）。
          </p>
          <div v-else-if="predict?.rows.length" class="table-wrap horizon-table">
            <table>
              <thead>
                <tr>
                  <th>#</th>
                  <th>标的</th>
                  <th>预测分</th>
                  <th>共振</th>
                  <th>涨跌%</th>
                  <th>封板</th>
                  <th>理由</th>
                  <th>操作</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(row, i) in predict.rows" :key="row.vt_symbol">
                  <td>{{ i + 1 }}</td>
                  <td>
                    {{ row.name || row.vt_symbol }}
                    <div class="mono muted tiny">{{ row.vt_symbol }}</div>
                  </td>
                  <td class="mono">{{ row.predict_score.toFixed(2) }}</td>
                  <td class="mono">{{ row.resonance_score.toFixed(1) }}</td>
                  <td class="mono">
                    {{ row.change_pct != null ? row.change_pct.toFixed(2) : '—' }}
                  </td>
                  <td class="muted tiny">{{ row.seal_time_label || '—' }}</td>
                  <td class="muted tiny">{{ (row.reasons || []).join(' · ') || '—' }}</td>
                  <td class="ops">
                    <button
                      type="button"
                      class="ghost tiny-btn"
                      @click="analysis.open(row.vt_symbol, row.name)"
                    >
                      析
                    </button>
                    <button
                      type="button"
                      class="ghost tiny-btn"
                      :disabled="!!actingVt"
                      @click="addWatchFromHorizonRow(row.vt_symbol, row.name)"
                    >
                      自选
                    </button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </template>
        <template v-else-if="horizonHasCache">
          <p class="muted">
            上次预测阶段失败或未写入，可于 Ops 重跑
            <code class="mono">scan_horizon_outlook</code>。
          </p>
          <RouterLink to="/ops" class="draft-link">去 Ops</RouterLink>
        </template>
        <template v-else>
          <p class="muted">
            暂无规则预测。请于 Ops 执行
            <code class="mono">scan_horizon_outlook</code>（与共振展望同 job）。
          </p>
          <RouterLink to="/ops" class="draft-link">去 Ops</RouterLink>
        </template>
      </div>

      <div class="workbench" :class="{ withSide: sideOpen }">
        <aside v-if="sideOpen" class="side">
          <div class="side-head">
            <strong>共振榜</strong>
            <span class="muted">≥2 卡 · 可调权重</span>
          </div>
          <div class="weight-head">
            <strong>权重</strong>
            <button class="ghost tiny-btn" type="button" @click="weightOpen = !weightOpen">
              {{ weightOpen ? '收起' : '展开' }}
            </button>
          </div>
          <div v-if="weightOpen" class="weight-panel">
            <div v-for="item in weightItems" :key="item.card_id" class="weight-row">
              <label :for="`w-${item.card_id}`">{{ item.title }}</label>
              <input
                :id="`w-${item.card_id}`"
                v-model.number="weightDraft[item.card_id]"
                type="number"
                min="0"
                max="5"
                step="0.1"
                :disabled="weightBusy"
              />
            </div>
            <p v-if="weightErr" class="weight-err">{{ weightErr }}</p>
            <div class="weight-actions">
              <button
                class="primary"
                type="button"
                :disabled="weightBusy || weightItems.length === 0"
                @click="saveWeights"
              >
                保存
              </button>
              <button class="ghost" type="button" :disabled="weightBusy" @click="resetWeights">
                恢复默认
              </button>
            </div>
          </div>
          <p v-if="sideMsg" class="side-msg">{{ sideMsg }}</p>
          <button class="primary full" type="button" @click="goLeaderScreen">龙头选股 → Hub</button>
          <button class="ghost full" type="button" @click="goResonanceScreen">
            共振选股 → Hub
          </button>
          <input
            v-if="resonance.length"
            v-model="resonanceFilter"
            class="side-filter"
            placeholder="过滤代码/名称"
          />
          <div class="side-list">
            <div v-for="(e, i) in displayedResonance" :key="e.vt_symbol" class="side-row">
              <div class="side-top">
                <span class="rank" :class="'rank-' + (i + 1)">{{ i + 1 }}</span>
                <div class="side-meta">
                  <div class="side-name">
                    <span v-if="e.card_count >= 2" class="star">★</span>
                    {{ e.name || e.vt_symbol }}
                  </div>
                  <div class="mono muted tiny">{{ e.vt_symbol }}</div>
                </div>
                <div class="side-score">{{ e.resonance_score.toFixed(1) }}</div>
              </div>
              <div class="muted tiny">
                {{ e.card_count }} 卡 · {{ e.card_titles.join(' / ') }}
                <template v-if="sealLabel(e)"> · {{ sealLabel(e) }}</template>
              </div>
              <div class="side-actions">
                <button type="button" class="link" @click="analysis.open(e.vt_symbol, e.name)">
                  析
                </button>
                <button
                  type="button"
                  class="link"
                  :disabled="actingVt === e.vt_symbol"
                  @click="addWatch(e.vt_symbol, e.name)"
                >
                  加自选
                </button>
              </div>
            </div>
            <p v-if="!resonance.length" class="muted empty-side">
              暂无共振标的（需至少 2 张卡片命中同一标的；可调权重后刷新）
            </p>
            <p v-else-if="!displayedResonance.length" class="muted empty-side">无匹配共振</p>
          </div>
        </aside>

        <main class="main">
          <template v-if="!loading && !error && !cards.length">
            <p class="muted empty-main">
              暂无雷达卡片。可点刷新，或于 Ops 手动执行 warm_radar_card_snapshots 预热缓存。
              <RouterLink to="/ops" class="draft-link">去 Ops</RouterLink>
            </p>
          </template>
          <template v-else>
            <div v-if="cards.length" class="card-tools">
              <div class="chips">
                <button
                  type="button"
                  class="chip"
                  :class="{ on: !sourceChip }"
                  @click="sourceChip = ''"
                >
                  全部
                </button>
                <button
                  v-for="s in sourceOptions"
                  :key="s"
                  type="button"
                  class="chip"
                  :class="{ on: sourceChip === s }"
                  @click="sourceChip = s"
                >
                  {{ sourceLabel(s) }}
                </button>
              </div>
              <div class="row filter-row">
                <input v-model="cardFilter" placeholder="过滤标题/来源" />
                <button
                  type="button"
                  class="ghost"
                  :class="{ on: !cardSortKey }"
                  @click="clearCardSort"
                >
                  默认序
                </button>
                <button type="button" class="ghost" @click="toggleCardSort('title')">
                  标题{{ cardSortMark('title') }}
                </button>
                <button type="button" class="ghost" @click="toggleCardSort('rows')">
                  行数{{ cardSortMark('rows') }}
                </button>
              </div>
            </div>
            <p v-if="cards.length && !displayedCards.length" class="muted empty-main">无匹配卡片</p>
            <div v-else class="grid">
              <button
                v-for="c in displayedCards"
                :key="c.card_id"
                type="button"
                class="card"
                :class="{ on: active?.card_id === c.card_id }"
                @click="activeId = c.card_id"
              >
                <div class="title-row">
                  <span class="title">{{ c.title }}</span>
                  <span v-if="cardResonanceCount(c) >= 2" class="res-badge" title="共振命中卡数">
                    ★{{ cardResonanceCount(c) }}
                  </span>
                </div>
                <div class="meta muted">{{ c.rows.length }} 行 · {{ sourceLabel(c.source) }}</div>
                <div v-if="c.empty_message && !c.rows.length" class="preview muted">
                  {{ c.empty_message }}
                </div>
                <div v-else-if="c.rows[0]" class="preview">{{ rowLabel(c.rows[0]) }}</div>
              </button>
            </div>
          </template>
        </main>

        <section class="detail-pane">
          <template v-if="active">
            <div class="pane-head">
              <h2>{{ active.title }}</h2>
              <span class="muted tiny"
                >{{ active.rows.length }} 行 · {{ sourceLabel(active.source) }}</span
              >
            </div>
            <p v-if="active.subtitle || active.empty_message" class="muted pane-sub">
              {{ active.subtitle }} {{ active.empty_message }}
            </p>
            <p v-if="detailMsg" class="detail-msg">{{ detailMsg }}</p>
            <div class="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>#</th>
                    <th>标的</th>
                    <th>细节</th>
                    <th>操作</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="(row, i) in active.rows" :key="i">
                    <td>{{ i + 1 }}</td>
                    <td>
                      <span v-if="rowResonanceCount(row) >= 2" class="star">★</span>
                      {{ rowLabel(row) }}
                    </td>
                    <td class="mono muted">
                      <template v-if="row.leader_tier">
                        {{ row.leader_tier }} · 评分 {{ Number(row.leader_score || 0).toFixed(0) }}
                        <template v-if="row.limit_times != null">
                          · {{ row.limit_times }}板</template
                        >
                        <template v-if="sealLabel(row)"> · {{ sealLabel(row) }}</template>
                      </template>
                      <template v-else-if="row.change_pct != null"
                        >涨幅 {{ Number(row.change_pct).toFixed(2) }}%</template
                      >
                      <template v-else-if="row.net_flow_yi != null"
                        >净流入 {{ Number(row.net_flow_yi).toFixed(2) }} 亿</template
                      >
                      <template v-else-if="row.limit_times != null">
                        {{ row.limit_times }} 板
                        <template v-if="sealLabel(row)"> · {{ sealLabel(row) }}</template>
                      </template>
                      <template v-else-if="row.role">{{ row.role }}</template>
                      <template v-else-if="sealLabel(row)">{{ sealLabel(row) }}</template>
                      <template v-else>—</template>
                    </td>
                    <td class="row-actions">
                      <template v-if="rowVt(row)">
                        <button
                          type="button"
                          class="tiny-btn"
                          :disabled="actingVt === rowVt(row)"
                          @click="addWatchFromDetail(rowVt(row), String(row.name || ''))"
                        >
                          加自选
                        </button>
                        <button type="button" class="tiny-btn" @click="openInWatchlist(rowVt(row))">
                          在自选打开
                        </button>
                        <button type="button" class="tiny-btn" @click="openInNotes(rowVt(row))">
                          去笔记
                        </button>
                      </template>
                      <template v-else>—</template>
                    </td>
                  </tr>
                  <tr v-if="!active.rows.length">
                    <td colspan="4" class="empty">{{ active.empty_message || '暂无行' }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </template>
          <div v-else class="empty-pane">
            <p class="muted">选择一张卡片查看详情</p>
          </div>
        </section>
      </div>
    </div>
  </AppShell>
  <StockAnalysisModal />
</template>

<style scoped>
.page {
  display: grid;
  gap: 12px;
  height: 100%;
  min-height: 0;
  box-sizing: border-box;
  padding: 16px 24px 24px;
}
.toolbar {
  display: flex;
  gap: 8px 12px;
  align-items: center;
  flex-wrap: wrap;
  padding: 10px 16px;
  border: 1px solid var(--line);
  border-radius: 0.75rem;
  background: var(--surface);
  box-shadow: var(--shadow-card);
}
.toolbar .spacer {
  flex: 1;
}
.toolbar .source-hint {
  white-space: nowrap;
}
.ghost {
  background: var(--surface);
  border: 1px solid var(--line);
  color: var(--ink-muted);
  border-radius: 0.5rem;
  padding: 7px 12px;
  font-size: 0.8125rem;
  cursor: pointer;
  transition:
    background 0.15s ease,
    color 0.15s ease,
    border-color 0.15s ease;
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
  border-color: var(--brand-soft);
  background: var(--brand-light);
  color: var(--brand);
  font-weight: 500;
}
.primary {
  background: var(--brand);
  border: none;
  color: var(--brand-foreground);
  border-radius: 0.5rem;
  padding: 7px 14px;
  font-size: 0.8125rem;
  font-weight: 600;
  cursor: pointer;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);
}
.primary:hover:not(:disabled) {
  background: var(--brand-dark);
}
.primary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.primary.full {
  width: 100%;
}
.ghost.full {
  width: 100%;
}
.err {
  margin: 0;
  color: var(--danger);
}
.draft-msg {
  margin: 0;
  font-size: 0.85rem;
  color: var(--brand);
  display: flex;
  gap: 10px;
  align-items: center;
  flex-wrap: wrap;
}
.draft-link {
  color: var(--brand);
  text-decoration: underline;
  font-size: 0.85rem;
}

/* 摘要条 */
.summary-bar {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 10px;
}
.summary-card {
  display: flex;
  align-items: center;
  gap: 8px;
  border: 1px solid var(--line);
  border-radius: 0.75rem;
  background: var(--surface);
  box-shadow: var(--shadow-card);
  padding: 8px 12px;
  cursor: pointer;
  text-align: left;
  transition:
    border-color 0.15s ease,
    background 0.15s ease;
}
.summary-card:hover {
  border-color: var(--brand-soft);
}
.summary-card.open {
  border-color: var(--brand-soft);
  background: var(--brand-light);
}
.summary-k {
  font-size: 0.85rem;
  font-weight: 600;
  white-space: nowrap;
}
.summary-v {
  font-size: 0.8rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.summary-t {
  font-size: 0.72rem;
  white-space: nowrap;
}
.chevron {
  margin-left: auto;
  color: var(--ink-faint);
  font-size: 0.7rem;
}
.summary-panel {
  border: 1px solid var(--line);
  border-radius: 0.75rem;
  background: var(--surface);
  box-shadow: var(--shadow-card);
  padding: 12px 16px;
}
.summary-panel-head {
  display: flex;
  align-items: baseline;
  gap: 8px;
  margin-bottom: 8px;
}
.summary-panel-head strong {
  font-size: 0.9rem;
  font-weight: 600;
}
.horizon-err {
  margin: 0;
  color: var(--danger);
  font-size: 0.85rem;
}
.horizon-table {
  margin-top: 8px;
}

/* 三栏工作台 */
.workbench {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  grid-template-areas: 'main' 'detail';
  gap: 12px;
  min-height: 0;
  align-items: start;
}
.workbench.withSide {
  grid-template-columns: 280px minmax(0, 1fr);
  grid-template-areas: 'side main' 'detail detail';
}
@media (min-width: 1280px) {
  .workbench.withSide {
    grid-template-columns: 280px minmax(0, 1fr) 380px;
    grid-template-areas: 'side main detail';
  }
  .workbench.withSide > * {
    max-height: calc(100vh - 200px);
    overflow: auto;
  }
}
.side {
  grid-area: side;
}
.detail-pane {
  grid-area: detail;
}

/* 主区 */
.main {
  grid-area: main;
  min-width: 0;
  display: grid;
  gap: 12px;
  align-content: start;
  padding: 14px 16px;
  border: 1px solid var(--line);
  border-radius: 0.75rem;
  background: var(--surface);
  box-shadow: var(--shadow-card);
}
.card-tools {
  display: grid;
  gap: 10px;
}
.chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.chip {
  border: 1px solid var(--line);
  background: var(--surface);
  color: var(--ink-muted);
  padding: 4px 12px;
  cursor: pointer;
  border-radius: 999px;
  font-size: 0.78rem;
  transition:
    background 0.15s ease,
    color 0.15s ease,
    border-color 0.15s ease;
}
.chip:hover {
  border-color: var(--brand-soft);
  color: var(--ink);
}
.chip.on {
  border-color: var(--brand-soft);
  background: var(--brand-light);
  color: var(--brand);
  font-weight: 500;
}
.filter-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}
.filter-row input {
  flex: 1;
  min-width: 140px;
  box-sizing: border-box;
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: 0.5rem;
  color: var(--ink);
  padding: 6px 10px;
  font-size: 0.85rem;
}
.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 10px;
}
.card {
  position: relative;
  text-align: left;
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: 0.75rem;
  box-shadow: var(--shadow-card);
  padding: 12px 14px;
  color: var(--ink);
  display: grid;
  gap: 5px;
  cursor: pointer;
  transition:
    border-color 0.15s ease,
    background 0.15s ease,
    box-shadow 0.15s ease,
    transform 0.15s ease;
}
.card:hover {
  border-color: var(--brand-soft);
  box-shadow: var(--shadow-panel);
  transform: translateY(-1px);
}
.card.on {
  border-color: var(--brand);
  background: var(--brand-light);
}
.card.on::before {
  content: '';
  position: absolute;
  left: 0;
  top: 12px;
  bottom: 12px;
  width: 3px;
  border-radius: 999px;
  background: var(--brand);
}
.title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
.title {
  font-weight: 600;
  font-size: 0.9rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.res-badge {
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  gap: 2px;
  padding: 1px 7px;
  border-radius: 999px;
  background: var(--brand);
  color: var(--brand-foreground);
  font-size: 0.7rem;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}
.meta {
  font-size: 0.75rem;
}
.preview {
  font-size: 0.8rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* 详情面板 */
.detail-pane {
  display: grid;
  gap: 8px;
  align-content: start;
  padding: 14px 16px;
  border: 1px solid var(--line);
  border-radius: 0.75rem;
  background: var(--surface);
  box-shadow: var(--shadow-card);
}
.pane-head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 10px;
}
.pane-head h2 {
  margin: 0;
  font-size: 1rem;
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.pane-sub {
  margin: 0;
}
.detail-msg {
  margin: 0;
  font-size: 0.85rem;
  color: var(--muted);
}
.empty-pane {
  display: grid;
  place-items: center;
  padding: 32px 8px;
  color: var(--ink-faint);
  font-size: 0.9rem;
}
.empty-pane p {
  margin: 0;
}
.row-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  white-space: nowrap;
}

/* 共振榜 */
.side {
  border: 1px solid var(--line);
  border-radius: 0.75rem;
  background: var(--surface);
  box-shadow: var(--shadow-card);
  padding: 14px;
  display: grid;
  gap: 10px;
  align-content: start;
}
.side-head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 8px;
  padding-bottom: 10px;
  border-bottom: 1px solid var(--line-soft);
}
.side-head strong {
  font-size: 0.9rem;
  font-weight: 600;
}
.weight-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
}
.weight-head strong {
  font-size: 0.85rem;
  font-weight: 600;
}
.tiny-btn {
  padding: 4px 8px;
  font-size: 0.75rem;
}
.weight-panel {
  border: 1px solid var(--line);
  border-radius: 0.5rem;
  padding: 8px;
  display: grid;
  gap: 8px;
  background: var(--surface-muted);
}
.weight-row {
  display: grid;
  grid-template-columns: 1fr 72px;
  gap: 8px;
  align-items: center;
  font-size: 0.8rem;
}
.weight-row input {
  width: 100%;
  box-sizing: border-box;
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: 0.375rem;
  color: var(--ink);
  padding: 4px 6px;
  font-variant-numeric: tabular-nums;
}
.weight-actions {
  display: flex;
  gap: 8px;
}
.weight-actions .primary,
.weight-actions .ghost {
  flex: 1;
}
.weight-err {
  margin: 0;
  font-size: 0.78rem;
  color: var(--danger);
}
.side-msg {
  margin: 0;
  font-size: 0.8rem;
  color: var(--brand);
}
.side-filter {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: 0.5rem;
  color: var(--ink);
  padding: 6px 10px;
  width: 100%;
  box-sizing: border-box;
}
.side-list {
  display: grid;
  gap: 8px;
}
.side-row {
  border: 1px solid var(--line);
  border-radius: 0.625rem;
  padding: 10px;
  display: grid;
  gap: 6px;
  background: var(--surface);
  transition:
    border-color 0.15s ease,
    background 0.15s ease;
}
.side-row:hover {
  border-color: var(--brand-soft);
  background: var(--brand-light);
}
.side-top {
  display: grid;
  grid-template-columns: 24px 1fr auto;
  gap: 6px;
  align-items: start;
}
.rank {
  display: inline-grid;
  place-items: center;
  min-width: 24px;
  height: 20px;
  border-radius: 999px;
  font-size: 0.72rem;
  font-weight: 600;
  color: var(--ink-muted);
  background: var(--surface-muted);
  font-variant-numeric: tabular-nums;
}
.rank.rank-1 {
  background: #fde8d7;
  color: #b45309;
}
.rank.rank-2 {
  background: #eef0f3;
  color: #52525b;
}
.rank.rank-3 {
  background: #fbe3dc;
  color: #9a5b3f;
}
.side-meta {
  min-width: 0;
}
.side-name {
  font-weight: 600;
  font-size: 0.9rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.star {
  color: var(--brand);
  margin-right: 2px;
}
.side-score {
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  padding: 2px 8px;
  border-radius: 999px;
  background: var(--brand-light);
  color: var(--brand);
  font-size: 0.8rem;
}
.link {
  justify-self: start;
  background: transparent;
  border: none;
  color: var(--brand);
  padding: 0;
  cursor: pointer;
  font-size: 0.8rem;
}
.link:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* 表格与通用 */
.table-wrap {
  border: 1px solid var(--line);
  border-radius: 0.75rem;
  overflow: auto;
  background: var(--surface);
  box-shadow: var(--shadow-card);
}
th,
td {
  padding: 8px 10px;
  border-bottom: 1px solid var(--line);
  font-size: 0.85rem;
  text-align: left;
  white-space: nowrap;
}
th {
  color: var(--ink-muted);
  background: var(--surface-muted);
  position: sticky;
  top: 0;
  font-weight: 500;
  z-index: 1;
}
tbody tr:hover td {
  background: var(--surface-muted);
}
.detail-pane .table-wrap tbody tr:hover td {
  background: var(--brand-light);
}
.mono {
  font-family: var(--mono);
}
.muted {
  color: var(--muted);
  font-size: 0.85rem;
}
.tiny {
  font-size: 0.72rem;
}
.empty {
  text-align: center;
  color: var(--muted);
  padding: 24px !important;
}
.empty-main {
  padding: 24px 8px;
  line-height: 1.6;
  margin: 0;
}
.empty-side {
  text-align: center;
  padding: 16px 8px;
  margin: 0;
}
.ops {
  white-space: nowrap;
}

@media (max-width: 900px) {
  .workbench,
  .workbench.withSide {
    grid-template-columns: 1fr;
    grid-template-areas: 'main' 'side' 'detail';
  }
}
</style>

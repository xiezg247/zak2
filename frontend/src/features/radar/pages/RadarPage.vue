<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import AppShell from '../../../components/AppShell.vue'
import StockAnalysisModal from '../../../components/StockAnalysisModal.vue'
import RadarSummaryPanels from '../components/RadarSummaryPanels.vue'
import RadarResonanceSide from '../components/RadarResonanceSide.vue'
import { fmtDateTime } from '../../../lib/format'
import {
  marketApi,
  type RadarCard,
  type RadarHorizon,
  type RadarPredict,
  type RadarResonanceEntry,
  type ResonanceWeightItem,
} from '../../../api/market'
import { watchlistApi } from '../../../api/watchlist'
import { useStockAnalysis } from '../../../composables/useStockAnalysis'

const analysis = useStockAnalysis()

const router = useRouter()
const cards = ref<RadarCard[]>([])
const resonance = ref<RadarResonanceEntry[]>([])
const activeId = ref('')
const error = ref('')
const loading = ref(false)
const sideOpen = ref(true)
const sideMsg = ref('')
const detailMsg = ref('')
const rowActionMsg = ref('')
const actingVt = ref('')
const weightItems = ref<ResonanceWeightItem[]>([])
const weightDraft = ref<Record<string, number>>({})
const weightBusy = ref(false)
const weightErr = ref('')
const horizon = ref<RadarHorizon | null>(null)
const horizonErr = ref('')
const predict = ref<RadarPredict | null>(null)
const predictErr = ref('')

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
  void router.push({
    path: '/screener/recipe',
    query: { recipe: 'radar_leader', variant: 'mainline' },
  })
}

function goResonanceScreen() {
  void router.push({ path: '/screener/recipe', query: { recipe: 'radar_resonance' } })
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

function openAnalysis(vt: string, name?: string) {
  analysis.open(vt, name)
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
          {{ fmtDateTime(active.computed_at) || active.subtitle || '—' }}</span
        >
      </div>
      <p v-if="error" class="err">{{ error }}</p>
      <p v-if="rowActionMsg" class="draft-msg">{{ rowActionMsg }}</p>

      <RadarSummaryPanels
        :horizon="horizon"
        :horizon-err="horizonErr"
        :predict="predict"
        :predict-err="predictErr"
        :acting-vt="actingVt"
        @analyze="openAnalysis"
        @add-watch="addWatchFromHorizonRow"
      />

      <div class="workbench" :class="{ withSide: sideOpen }">
        <RadarResonanceSide
          v-if="sideOpen"
          :resonance="resonance"
          :weight-items="weightItems"
          v-model:weight-draft="weightDraft"
          :weight-busy="weightBusy"
          :weight-err="weightErr"
          :side-msg="sideMsg"
          :acting-vt="actingVt"
          @save-weights="saveWeights"
          @reset-weights="resetWeights"
          @go-leader="goLeaderScreen"
          @go-resonance="goResonanceScreen"
          @analyze="openAnalysis"
          @add-watch="addWatch"
        />

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

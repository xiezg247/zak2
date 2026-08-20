<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import AppShell from '../../../components/AppShell.vue'
import StockAnalysisModal from '../../analysis/components/StockAnalysisModal.vue'
import RadarSummaryPanels from '../components/RadarSummaryPanels.vue'
import RadarResonanceSide from '../components/RadarResonanceSide.vue'
import RadarCardsPanel from '../components/RadarCardsPanel.vue'
import RadarDetailPane from '../components/RadarDetailPane.vue'
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
import { useStockAnalysis } from '../../analysis/composables/useStockAnalysis'

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

const SOURCE_LABELS: Record<string, string> = {
  cache: '缓存',
  synthesized: '合成',
}

function sourceLabel(source: string): string {
  return SOURCE_LABELS[source] || source
}

const active = computed(() => {
  if (!activeId.value) return null
  return cards.value.find((c) => c.card_id === activeId.value) || null
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

function openInWatchlist(vt: string) {
  void router.push({ path: '/watchlist', query: { symbol: vt } })
}

function openInNotes(vt: string) {
  void router.push({ path: '/notes', query: { symbol: vt } })
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

function openCard(cardId: string) {
  activeId.value = cardId
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

        <RadarCardsPanel
          :cards="cards"
          :loading="loading"
          :error="error"
          :active-id="activeId"
          :card-count-by-vt="cardCountByVt"
          @open-card="openCard"
        />

        <RadarDetailPane
          :active="active"
          :detail-msg="detailMsg"
          :acting-vt="actingVt"
          :card-count-by-vt="cardCountByVt"
          @add-watch="addWatchFromDetail"
          @open-watchlist="openInWatchlist"
          @open-notes="openInNotes"
        />
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
.muted {
  color: var(--muted);
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

@media (max-width: 900px) {
  .workbench,
  .workbench.withSide {
    grid-template-columns: 1fr;
    grid-template-areas: 'main' 'side' 'detail';
  }
}
</style>

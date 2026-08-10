<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import AppShell from '../components/AppShell.vue'
import {
  marketApi,
  type RadarCard,
  type RadarResonanceEntry,
  type ResonanceWeightItem,
} from '../api/market'
import { watchlistApi } from '../api/watchlist'

const router = useRouter()
const cards = ref<RadarCard[]>([])
const resonance = ref<RadarResonanceEntry[]>([])
const activeId = ref('')
const error = ref('')
const loading = ref(false)
const sideOpen = ref(true)
const sideMsg = ref('')
const actingVt = ref('')
const weightOpen = ref(false)
const weightItems = ref<ResonanceWeightItem[]>([])
const weightDraft = ref<Record<string, number>>({})
const weightBusy = ref(false)
const weightErr = ref('')
const draftBusy = ref(false)
const draftMsg = ref('')

const active = computed(() => cards.value.find((c) => c.card_id === activeId.value) || cards.value[0] || null)

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
  const weightsPromise = marketApi.resonanceWeights().catch((e) => {
    weightErr.value = e instanceof Error ? e.message : '权重加载失败'
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
  const w = await weightsPromise
  if (w) {
    applyWeights(w)
    weightErr.value = ''
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

function sealLabel(row: Record<string, unknown> | { seal_time_label?: string; first_time?: string }) {
  const label = String(row.seal_time_label || '').trim()
  if (label) return label
  const ft = String((row as { first_time?: string }).first_time || '').trim()
  if (ft.length >= 4) return `${ft.slice(0, 2)}:${ft.slice(2, 4)} 封板`
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

function rowResonanceCount(row: Record<string, unknown>): number {
  for (const k of rowVtKeys(row)) {
    const n = cardCountByVt.value.get(k)
    if (typeof n === 'number') return n
  }
  return 0
}

function goLeaderScreen() {
  void router.push({ path: '/screener', query: { recipe: 'radar_leader', variant: 'mainline' } })
}

function goResonanceScreen() {
  void router.push({ path: '/screener', query: { recipe: 'radar_resonance' } })
}

async function createPlanDraft() {
  if (draftBusy.value) return
  draftBusy.value = true
  draftMsg.value = ''
  try {
    const r = await marketApi.createPlanDraft()
    draftMsg.value = `已写入 draft · ${r.trade_date} · ${r.symbol_count} 只${r.replaced ? '（已覆盖）' : ''}`
  } catch (e) {
    draftMsg.value = e instanceof Error ? e.message : '生成草案失败'
  } finally {
    draftBusy.value = false
  }
}

async function addWatch(vt: string, name?: string) {
  if (!vt || actingVt.value) return
  actingVt.value = vt
  sideMsg.value = ''
  try {
    await watchlistApi.add(vt, name || '')
    sideMsg.value = `已加入自选 ${vt}`
  } catch (e) {
    sideMsg.value = e instanceof Error ? e.message : '加自选失败'
  } finally {
    actingVt.value = ''
  }
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
        <button class="primary" type="button" @click="goLeaderScreen">龙头选股 → Hub</button>
        <button class="ghost" type="button" @click="goResonanceScreen">共振选股 → Hub</button>
        <button class="ghost" type="button" :disabled="draftBusy || loading" @click="createPlanDraft">
          生成次日计划草案
        </button>
        <button class="ghost" type="button" @click="sideOpen = !sideOpen">
          {{ sideOpen ? '收起共振' : '展开共振' }}
        </button>
        <span class="muted" v-if="active">来源 {{ active.source }} · {{ active.computed_at || active.subtitle || '—' }}</span>
      </div>
      <p v-if="error" class="err">{{ error }}</p>
      <p v-if="draftMsg" class="draft-msg">
        {{ draftMsg }}
        <RouterLink v-if="draftMsg.startsWith('已写入')" to="/playbook" class="draft-link">去守则看计划</RouterLink>
      </p>

      <div class="body" :class="{ withSide: sideOpen }">
        <div class="main">
          <div class="grid">
            <button
              v-for="c in cards"
              :key="c.card_id"
              type="button"
              class="card"
              :class="{ on: active?.card_id === c.card_id }"
              @click="activeId = c.card_id"
            >
              <div class="title">{{ c.title }}</div>
              <div class="meta muted">{{ c.rows.length }} 行 · {{ c.source }}</div>
              <div class="preview muted" v-if="c.empty_message && !c.rows.length">{{ c.empty_message }}</div>
              <div class="preview" v-else-if="c.rows[0]">{{ rowLabel(c.rows[0]) }}</div>
            </button>
          </div>

          <section class="detail" v-if="active">
            <h2>{{ active.title }}</h2>
            <p class="muted" v-if="active.subtitle || active.empty_message">
              {{ active.subtitle }} {{ active.empty_message }}
            </p>
            <div class="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>#</th>
                    <th>标的</th>
                    <th>细节</th>
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
                        <template v-if="row.limit_times != null"> · {{ row.limit_times }}板</template>
                        <template v-if="sealLabel(row)"> · {{ sealLabel(row) }}</template>
                      </template>
                      <template v-else-if="row.change_pct != null">涨幅 {{ Number(row.change_pct).toFixed(2) }}%</template>
                      <template v-else-if="row.net_flow_yi != null">净流入 {{ Number(row.net_flow_yi).toFixed(2) }} 亿</template>
                      <template v-else-if="row.limit_times != null">
                        {{ row.limit_times }} 板
                        <template v-if="sealLabel(row)"> · {{ sealLabel(row) }}</template>
                      </template>
                      <template v-else-if="row.role">{{ row.role }}</template>
                      <template v-else-if="sealLabel(row)">{{ sealLabel(row) }}</template>
                      <template v-else>—</template>
                    </td>
                  </tr>
                  <tr v-if="!active.rows.length">
                    <td colspan="3" class="empty">{{ active.empty_message || '暂无行' }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </section>
        </div>

        <aside v-if="sideOpen" class="side">
          <div class="side-head">
            <strong>共振</strong>
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
              <button class="ghost" type="button" :disabled="weightBusy" @click="resetWeights">恢复默认</button>
            </div>
          </div>
          <p v-if="sideMsg" class="side-msg">{{ sideMsg }}</p>
          <button class="primary full" type="button" @click="goLeaderScreen">龙头选股 → Hub</button>
          <button class="ghost full" type="button" @click="goResonanceScreen">共振选股 → Hub</button>
          <div class="side-list">
            <div v-for="(e, i) in resonance" :key="e.vt_symbol" class="side-row">
              <div class="side-top">
                <span class="rank">{{ i + 1 }}</span>
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
              <button
                type="button"
                class="link"
                :disabled="actingVt === e.vt_symbol"
                @click="addWatch(e.vt_symbol, e.name)"
              >
                加自选
              </button>
            </div>
            <p v-if="!resonance.length" class="muted empty-side">暂无共振（刷新雷达卡片后再试）</p>
          </div>
        </aside>
      </div>
    </div>
  </AppShell>
</template>

<style scoped>
.page {
  padding: 16px 20px;
  display: grid;
  gap: 14px;
  height: 100%;
  min-height: 0;
  box-sizing: border-box;
}
.toolbar {
  display: flex;
  gap: 12px;
  align-items: center;
  flex-wrap: wrap;
}
.ghost {
  background: transparent;
  border: 1px solid var(--border);
  color: var(--text);
  border-radius: 8px;
  padding: 6px 10px;
}
.primary {
  background: var(--accent);
  border: none;
  color: #0b1020;
  border-radius: 8px;
  padding: 6px 12px;
  font-weight: 600;
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
  color: var(--accent);
  display: flex;
  gap: 10px;
  align-items: center;
  flex-wrap: wrap;
}
.draft-link {
  color: var(--accent);
  text-decoration: underline;
  font-size: 0.85rem;
}
.muted {
  color: var(--muted);
  font-size: 0.85rem;
}
.tiny {
  font-size: 0.72rem;
}
.body {
  display: grid;
  gap: 14px;
  min-height: 0;
}
.body.withSide {
  grid-template-columns: 1fr 280px;
}
.main {
  display: grid;
  gap: 14px;
  min-width: 0;
}
.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 10px;
}
.card {
  text-align: left;
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 12px;
  color: var(--text);
  display: grid;
  gap: 4px;
}
.card.on {
  border-color: var(--accent);
}
.title {
  font-weight: 600;
}
.preview {
  font-size: 0.85rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.detail h2 {
  margin: 0 0 6px;
  font-size: 1.1rem;
}
.table-wrap {
  border: 1px solid var(--border);
  border-radius: 10px;
  overflow: auto;
  background: var(--bg-elevated);
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
  background: #121924;
  font-weight: 500;
}
.mono {
  font-family: var(--mono);
}
.empty {
  text-align: center;
  color: var(--muted);
  padding: 24px !important;
}
.side {
  border: 1px solid var(--border);
  border-radius: 10px;
  background: var(--bg-elevated);
  padding: 12px;
  display: grid;
  gap: 10px;
  align-content: start;
  max-height: calc(100vh - 140px);
  overflow: auto;
}
.side-head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 8px;
}
.weight-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
}
.tiny-btn {
  padding: 4px 8px;
  font-size: 0.75rem;
}
.weight-panel {
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 8px;
  display: grid;
  gap: 8px;
  background: var(--bg);
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
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: 6px;
  color: var(--text);
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
  color: var(--accent);
}
.side-list {
  display: grid;
  gap: 10px;
}
.side-row {
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 8px;
  display: grid;
  gap: 4px;
  background: var(--bg);
}
.side-top {
  display: grid;
  grid-template-columns: 24px 1fr auto;
  gap: 6px;
  align-items: start;
}
.rank {
  color: var(--muted);
  font-variant-numeric: tabular-nums;
}
.side-name {
  font-weight: 600;
  font-size: 0.9rem;
}
.star {
  color: var(--accent);
  margin-right: 2px;
}
.side-score {
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}
.link {
  justify-self: start;
  background: transparent;
  border: none;
  color: var(--accent);
  padding: 0;
  cursor: pointer;
  font-size: 0.8rem;
}
.empty-side {
  text-align: center;
  padding: 16px 8px;
  margin: 0;
}
@media (max-width: 900px) {
  .body.withSide {
    grid-template-columns: 1fr;
  }
}
</style>

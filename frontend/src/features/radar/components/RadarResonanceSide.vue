<script setup lang="ts">
import { computed, ref } from 'vue'
import type { RadarResonanceEntry, ResonanceWeightItem } from '../../../api/market'

const props = defineProps<{
  resonance: RadarResonanceEntry[]
  weightItems: ResonanceWeightItem[]
  weightDraft: Record<string, number>
  weightBusy: boolean
  weightErr: string
  sideMsg: string
  actingVt: string
}>()

const emit = defineEmits<{
  'update:weightDraft': [v: Record<string, number>]
  saveWeights: []
  resetWeights: []
  goLeader: []
  goResonance: []
  analyze: [vt: string, name?: string]
  addWatch: [vt: string, name?: string]
}>()

const weightOpen = ref(false)
const resonanceFilter = ref('')

const displayedResonance = computed(() => {
  const q = resonanceFilter.value.trim().toLowerCase()
  if (!q) return props.resonance
  return props.resonance.filter((e) => {
    const vt = (e.vt_symbol || '').toLowerCase()
    const name = (e.name || '').toLowerCase()
    return vt.includes(q) || name.includes(q)
  })
})

function sealLabel(row: { seal_time_label?: string; first_time?: string }): string {
  const label = String(row.seal_time_label || '').trim()
  if (label) return label
  const ft = String(row.first_time || '').trim()
  if (ft.length >= 4) return `${ft.slice(0, 2)}:${ft.slice(2, 4)} 封板`
  return ''
}

function setWeight(cardId: string, v: number) {
  emit('update:weightDraft', { ...props.weightDraft, [cardId]: v })
}
</script>

<template>
  <aside class="side">
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
          type="number"
          min="0"
          max="5"
          step="0.1"
          :value="weightDraft[item.card_id]"
          :disabled="weightBusy"
          @input="setWeight(item.card_id, Number(($event.target as HTMLInputElement).value))"
        />
      </div>
      <p v-if="weightErr" class="weight-err">{{ weightErr }}</p>
      <div class="weight-actions">
        <button
          class="primary"
          type="button"
          :disabled="weightBusy || weightItems.length === 0"
          @click="emit('saveWeights')"
        >
          保存
        </button>
        <button class="ghost" type="button" :disabled="weightBusy" @click="emit('resetWeights')">
          恢复默认
        </button>
      </div>
    </div>
    <p v-if="sideMsg" class="side-msg">{{ sideMsg }}</p>
    <button class="primary full" type="button" @click="emit('goLeader')">龙头选股 → Hub</button>
    <button class="ghost full" type="button" @click="emit('goResonance')">共振选股 → Hub</button>
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
          <button type="button" class="link" @click="emit('analyze', e.vt_symbol, e.name)">析</button>
          <button
            type="button"
            class="link"
            :disabled="actingVt === e.vt_symbol"
            @click="emit('addWatch', e.vt_symbol, e.name)"
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
</template>

<style scoped>

.side {
  grid-area: side;
  border: 1px solid var(--line);
  border-radius: 0.75rem;
  background: var(--surface);
  box-shadow: var(--shadow-card);
  padding: 12px;
  overflow: auto;
  display: grid;
  gap: 10px;
  align-content: start;
}
.side-head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 8px;
}
.side-head strong {
  font-size: 0.9rem;
}
.weight-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  font-size: 0.85rem;
}
.weight-head strong {
  font-size: 0.85rem;
}
.tiny-btn {
  padding: 2px 8px;
  font-size: 0.75rem;
}
.weight-panel {
  border: 1px solid var(--border);
  border-radius: 0.5rem;
  padding: 8px;
  display: grid;
  gap: 8px;
  background: var(--bg-panel, var(--bg-elevated));
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
  padding: 4px 6px;
}
.weight-actions {
  display: flex;
  gap: 8px;
}
.weight-actions .primary,
.weight-actions .ghost {
  flex: 1;
  padding: 6px 8px;
  font-size: 0.8rem;
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
  width: 100%;
  box-sizing: border-box;
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: 0.5rem;
  color: var(--ink);
  padding: 6px 10px;
  font-size: 0.85rem;
}
.side-list {
  display: grid;
  gap: 8px;
}
.side-row {
  border: 1px solid var(--line);
  border-radius: 0.5rem;
  padding: 8px 10px;
  display: grid;
  gap: 4px;
  background: var(--surface-muted);
}
.side-row:hover {
  border-color: var(--brand-soft);
}
.side-top {
  display: flex;
  align-items: flex-start;
  gap: 8px;
}
.rank {
  width: 22px;
  height: 22px;
  border-radius: 999px;
  display: inline-grid;
  place-items: center;
  font-size: 0.7rem;
  font-weight: 600;
  background: var(--surface);
  border: 1px solid var(--line);
  color: var(--ink-muted);
  flex-shrink: 0;
}
.rank-1, .rank-2, .rank-3 {
  background: var(--brand-light);
  border-color: var(--brand-soft);
  color: var(--brand);
}
.side-meta {
  flex: 1;
  min-width: 0;
}
.side-name {
  font-size: 0.85rem;
  font-weight: 500;
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
.side-actions {
  display: flex;
  gap: 10px;
}
.star {
  color: var(--brand);
  margin-right: 2px;
}
.muted {
  color: var(--muted);
  font-size: 0.75rem;
}
.tiny {
  font-size: 0.72rem;
}
.mono {
  font-family: var(--mono);
}
.empty-side {
  margin: 8px 0 0;
}
.link {
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
.ghost {
  background: var(--surface);
  border: 1px solid var(--line);
  color: var(--ink-muted);
  border-radius: 0.5rem;
  padding: 7px 12px;
  font-size: 0.8125rem;
  cursor: pointer;
}
.ghost:disabled {
  opacity: 0.5;
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
}
.primary:disabled {
  opacity: 0.5;
}
.primary.full, .ghost.full {
  width: 100%;
}

</style>

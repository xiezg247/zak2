<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'
import type { RadarCard } from '../../../api/market'

const props = defineProps<{
  cards: RadarCard[]
  loading: boolean
  error: string
  activeId: string
  cardCountByVt: Map<string, number>
}>()

const emit = defineEmits<{
  openCard: [cardId: string]
}>()

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
  for (const c of props.cards) {
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
  let list = props.cards
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

watch(displayedCards, (list) => {
  if (!list.length) {
    if (props.cards.length) emit('openCard', '')
    return
  }
  if (!list.some((c) => c.card_id === props.activeId)) {
    emit('openCard', list[0].card_id)
  }
})

function rowLabel(row: Record<string, unknown>) {
  return String(row.name || row.vt_symbol || row.tf_symbol || row.sector_id || '—')
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
    const n = props.cardCountByVt.get(k)
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
</script>

<template>
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
          :class="{ on: activeId === c.card_id }"
          @click="emit('openCard', c.card_id)"
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
</template>

<style scoped>
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
.ghost.on {
  border-color: var(--brand-soft);
  background: var(--brand-light);
  color: var(--brand);
  font-weight: 500;
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
.muted {
  color: var(--muted);
  font-size: 0.85rem;
}
.empty-main {
  padding: 24px 8px;
  line-height: 1.6;
  margin: 0;
}
.draft-link {
  color: var(--brand);
  text-decoration: underline;
  font-size: 0.85rem;
}
</style>

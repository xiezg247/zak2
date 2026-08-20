<script setup lang="ts">
import { computed, ref } from 'vue'
import type { SectorFlowRow } from '../../../api/market'
import { cmpNullable } from '../../../lib/sort'

const props = defineProps<{
  rows: SectorFlowRow[]
  loading: boolean
  error: string
}>()

type SortKey = 'change_pct' | 'net_flow_yi' | null

const listFilter = ref('')
const sortKey = ref<SortKey>(null)
const sortDir = ref<'asc' | 'desc'>('desc')

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

const displayedRows = computed(() => {
  const q = listFilter.value.trim().toLowerCase()
  let list = props.rows
  if (q) {
    list = list.filter((r) => {
      const name = (r.name || '').toLowerCase()
      const id = (r.sector_id || '').toLowerCase()
      return name.includes(q) || id.includes(q)
    })
  }
  const key = sortKey.value
  if (!key) return list
  const dir = sortDir.value
  return [...list].sort((a, b) => cmpNullable(a[key], b[key], dir))
})

const maxAbsFlow = computed(() => {
  let m = 0
  for (const r of props.rows) {
    const a = Math.abs(r.net_flow_yi)
    if (a > m) m = a
  }
  return m || 1
})

function flowBarWidth(v: number): string {
  return `${Math.min(100, (Math.abs(v) / maxAbsFlow.value) * 100)}%`
}
</script>

<template>
  <div class="flow-block">
    <div v-if="rows.length" class="filter-row">
      <input v-model="listFilter" placeholder="过滤名称/ID" />
      <span v-if="sortKey" class="muted tiny"
        >已按 {{ sortKey === 'net_flow_yi' ? '净流入' : '涨幅' }} 排序</span
      >
      <button type="button" class="ghost" :class="{ on: !sortKey }" @click="clearSort">
        默认序
      </button>
    </div>

    <p v-if="loading" class="muted">加载中…</p>
    <p v-else-if="!error && !rows.length" class="muted empty-hint">
      暂无板块资金。可先到 Ops 执行 sync_sector_flow_daily。
      <RouterLink to="/ops" class="draft-link">去 Ops</RouterLink>
    </p>
    <p v-else-if="rows.length && !displayedRows.length" class="muted empty-hint">无匹配板块</p>

    <div v-if="displayedRows.length" class="table-wrap">
      <table>
        <thead>
          <tr>
            <th class="col-rank">#</th>
            <th>名称</th>
            <th class="sortable" @click="toggleSort('change_pct')">
              涨幅%{{ sortMark('change_pct') }}
            </th>
            <th class="sortable col-flow" @click="toggleSort('net_flow_yi')">
              净流入(亿){{ sortMark('net_flow_yi') }}
            </th>
            <th class="col-id">ID</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(r, i) in displayedRows" :key="r.sector_id">
            <td class="col-rank">
              <span class="rank-badge" :class="'rank-' + (i + 1)">{{ i + 1 }}</span>
            </td>
            <td class="name">{{ r.name }}</td>
            <td :class="{ up: r.change_pct > 0, down: r.change_pct < 0 }">
              {{ r.change_pct > 0 ? '+' : '' }}{{ r.change_pct.toFixed(2) }}
            </td>
            <td class="col-flow">
              <div class="flow-cell" :class="{ pos: r.net_flow_yi > 0, neg: r.net_flow_yi < 0 }">
                <span class="flow-track">
                  <span
                    class="flow-bar"
                    :class="{ pos: r.net_flow_yi > 0, neg: r.net_flow_yi < 0 }"
                    :style="{ width: flowBarWidth(r.net_flow_yi) }"
                  ></span>
                </span>
                <span class="flow-value mono"
                  >{{ r.net_flow_yi > 0 ? '+' : '' }}{{ r.net_flow_yi.toFixed(2) }}</span
                >
              </div>
            </td>
            <td class="mono muted col-id">{{ r.sector_id }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<style scoped>
.flow-block {
  display: grid;
  gap: 14px;
}
.filter-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}
.filter-row input {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: 0.5rem;
  color: var(--ink);
  padding: 7px 10px;
  min-width: 180px;
  font-size: 0.8125rem;
}
.filter-row input:focus {
  border-color: var(--brand);
  box-shadow: 0 0 0 3px rgba(230, 100, 50, 0.15);
  outline: none;
}
.tiny {
  font-size: 0.75rem;
}
.ghost {
  background: var(--surface);
  border: 1px solid var(--line);
  color: var(--ink-muted);
  border-radius: 0.5rem;
  padding: 6px 10px;
  cursor: pointer;
  font-size: 0.8125rem;
}
.ghost.on {
  border-color: var(--brand);
  color: var(--ink);
  font-weight: 500;
}
.muted {
  color: var(--muted);
  font-size: 0.85rem;
}
.empty-hint {
  margin: 0;
  padding: 12px 0;
}
.table-wrap {
  border: 1px solid var(--line);
  border-radius: 0.75rem;
  overflow: auto;
  background: var(--surface);
  box-shadow: var(--shadow-card);
  max-height: 72vh;
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
}
th.sortable {
  cursor: pointer;
  user-select: none;
}
th.sortable:hover {
  color: var(--ink);
}
tbody tr:hover td {
  background: var(--surface-muted);
}
.col-rank {
  width: 40px;
  text-align: center;
}
.col-flow {
  width: 200px;
}
.col-id {
  width: 120px;
}
.name {
  font-weight: 500;
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
.flow-cell {
  display: flex;
  align-items: center;
  gap: 8px;
}
.flow-track {
  flex: 1;
  height: 6px;
  border-radius: 999px;
  background: var(--line-soft);
  overflow: hidden;
}
.flow-bar {
  display: block;
  height: 100%;
  border-radius: 999px;
}
.flow-bar.pos {
  background: linear-gradient(90deg, #f5936a, var(--danger));
}
.flow-bar.neg {
  background: linear-gradient(90deg, #7fd6a4, var(--ok));
}
.flow-value {
  min-width: 64px;
  text-align: right;
  font-variant-numeric: tabular-nums;
  font-size: 0.82rem;
}
.flow-value.pos {
  color: var(--danger);
}
.flow-value.neg {
  color: var(--ok);
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
.draft-link {
  color: var(--brand);
  margin-left: 4px;
}
</style>

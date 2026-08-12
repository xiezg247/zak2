<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import AppShell from '../components/AppShell.vue'
import { marketApi, type SectorFlowRow } from '../api/market'

const kind = ref<'industry' | 'concept'>('concept')
const sort = ref<'net_flow_yi' | 'change_pct'>('net_flow_yi')
const dates = ref<string[]>([])
const tradeDate = ref('')
const rows = ref<SectorFlowRow[]>([])
const error = ref('')
const loading = ref(false)

type SortKey = 'change_pct' | 'net_flow_yi' | null

const listFilter = ref('')
const sortKey = ref<SortKey>(null)
const sortDir = ref<'asc' | 'desc'>('desc')

function cmpNullable(a: number | null | undefined, b: number | null | undefined, dir: 'asc' | 'desc'): number {
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

const displayedRows = computed(() => {
  const q = listFilter.value.trim().toLowerCase()
  let list = rows.value
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

const subtitle = computed(() => {
  if (!rows.value.length) return tradeDate.value || ''
  return `${tradeDate.value || rows.value[0].trade_date} · ${kind.value === 'concept' ? '概念' : '行业'}`
})

async function loadDates() {
  dates.value = await marketApi.sectorDates()
  if (!tradeDate.value && dates.value.length) tradeDate.value = dates.value[0]
}

async function loadFlow() {
  loading.value = true
  error.value = ''
  try {
    rows.value = await marketApi.sectorFlow({
      kind: kind.value,
      trade_date: tradeDate.value || undefined,
      sort: sort.value,
      limit: 80,
    })
  } catch (e) {
    error.value = e instanceof Error ? e.message : '加载失败'
  } finally {
    loading.value = false
  }
}

watch([kind, sort, tradeDate], () => {
  void loadFlow()
})

onMounted(async () => {
  try {
    await loadDates()
    await loadFlow()
  } catch (e) {
    error.value = e instanceof Error ? e.message : '加载失败'
  }
})
</script>

<template>
  <AppShell title="板块资金" :subtitle="subtitle" active="sectors">
    <div class="page">
      <div class="toolbar">
        <div class="tabs">
          <button type="button" :class="{ on: kind === 'concept' }" @click="kind = 'concept'">概念</button>
          <button type="button" :class="{ on: kind === 'industry' }" @click="kind = 'industry'">行业</button>
        </div>
        <div class="tabs">
          <button type="button" :class="{ on: sort === 'net_flow_yi' }" @click="sort = 'net_flow_yi'">净流入</button>
          <button type="button" :class="{ on: sort === 'change_pct' }" @click="sort = 'change_pct'">涨幅</button>
        </div>
        <select v-model="tradeDate">
          <option v-for="d in dates" :key="d" :value="d">{{ d }}</option>
        </select>
      </div>

      <p v-if="error" class="err">{{ error }}</p>

      <div v-if="rows.length" class="filter-row">
        <input v-model="listFilter" placeholder="过滤名称/ID" />
        <button type="button" class="ghost" :class="{ on: !sortKey }" @click="clearSort">默认序</button>
      </div>

      <p v-if="loading" class="muted">加载中…</p>
      <p v-else-if="!error && !rows.length" class="muted empty-hint">
        暂无板块资金。可先到 Ops 执行 sync_sector_flow_daily。
      </p>
      <p v-else-if="rows.length && !displayedRows.length" class="muted empty-hint">无匹配板块</p>

      <div v-if="displayedRows.length" class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>#</th>
              <th>名称</th>
              <th class="sortable" @click="toggleSort('change_pct')">涨幅%{{ sortMark('change_pct') }}</th>
              <th class="sortable" @click="toggleSort('net_flow_yi')">净流入(亿){{ sortMark('net_flow_yi') }}</th>
              <th>ID</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(r, i) in displayedRows" :key="r.sector_id">
              <td>{{ i + 1 }}</td>
              <td>{{ r.name }}</td>
              <td :class="{ up: r.change_pct > 0, down: r.change_pct < 0 }">{{ r.change_pct.toFixed(2) }}</td>
              <td :class="{ up: r.net_flow_yi > 0, down: r.net_flow_yi < 0 }">{{ r.net_flow_yi.toFixed(2) }}</td>
              <td class="mono muted">{{ r.sector_id }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </AppShell>
</template>

<style scoped>
.page {
  display: grid;
  gap: 14px;
}
.toolbar {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  align-items: center;
}
.tabs {
  display: flex;
  gap: 6px;
}
.tabs button {
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  color: var(--muted);
  border-radius: 0.5rem;
  padding: 6px 10px;
}
.tabs button.on {
  background: var(--brand-light);
  color: var(--brand);
  border-color: var(--brand-soft);
  font-weight: 500;
}
select {
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: 0.5rem;
  color: var(--text);
  padding: 6px 10px;
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
.ghost {
  background: transparent;
  border: 1px solid var(--border);
  color: var(--muted);
  border-radius: 0.5rem;
  padding: 6px 10px;
  cursor: pointer;
}
.ghost.on {
  border-color: var(--brand, #333);
  color: var(--text);
  font-weight: 500;
}
.err {
  margin: 0;
  color: var(--danger);
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
.mono {
  font-family: var(--mono);
}
.up {
  color: var(--danger);
}
.down {
  color: var(--ok);
}
</style>

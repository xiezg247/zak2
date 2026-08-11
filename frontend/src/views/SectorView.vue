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
      <p v-if="loading" class="muted">加载中…</p>

      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>#</th>
              <th>名称</th>
              <th>涨幅%</th>
              <th>净流入(亿)</th>
              <th>ID</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(r, i) in rows" :key="r.sector_id">
              <td>{{ i + 1 }}</td>
              <td>{{ r.name }}</td>
              <td :class="{ up: r.change_pct > 0, down: r.change_pct < 0 }">{{ r.change_pct.toFixed(2) }}</td>
              <td :class="{ up: r.net_flow_yi > 0, down: r.net_flow_yi < 0 }">{{ r.net_flow_yi.toFixed(2) }}</td>
              <td class="mono muted">{{ r.sector_id }}</td>
            </tr>
            <tr v-if="!rows.length">
              <td colspan="5" class="empty">暂无板块资金</td>
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
.err {
  margin: 0;
  color: var(--danger);
}
.muted {
  color: var(--muted);
  font-size: 0.85rem;
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
</style>

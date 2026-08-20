<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import AppShell from '../../../components/AppShell.vue'
import { marketApi, type SectorFlowRow } from '../../../api/market'
import SectorToolbar from '../components/SectorToolbar.vue'
import SectorFlowTable from '../components/SectorFlowTable.vue'

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
      <SectorToolbar
        v-model:kind="kind"
        v-model:sort="sort"
        v-model:trade-date="tradeDate"
        :dates="dates"
      />

      <p v-if="error" class="err">{{ error }}</p>

      <SectorFlowTable :rows="rows" :loading="loading" :error="error" />
    </div>
  </AppShell>
</template>

<style scoped>
.page {
  display: grid;
  gap: 14px;
  padding: 16px 24px 24px;
}
.err {
  margin: 0;
  color: var(--danger);
}
</style>

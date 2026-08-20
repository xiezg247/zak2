<script setup lang="ts">
import PagerBar from '../../../components/PagerBar.vue'
import { fmtDateTime } from '../../../lib/format'
import type { RunSummary } from '../../../api/screener'

defineProps<{
  history: RunSummary[]
  currentId?: string
  page: number
  pages: number
  total: number
  busy: boolean
  err: string
  runBusy: boolean
}>()

const emit = defineEmits<{
  refresh: []
  open: [id: string]
  page: [page: number]
}>()
</script>

<template>
  <div class="cfg-card">
    <div class="history-head">
      <strong>运行历史</strong>
      <span class="muted">{{ total ? `${total} 条` : '' }}</span>
      <button type="button" class="ghost tiny-btn" :disabled="busy" @click="emit('refresh')">
        {{ busy ? '刷新中…' : '刷新' }}
      </button>
    </div>
    <p v-if="err" class="err">{{ err }}</p>
    <p v-else-if="!busy && !history.length" class="muted">暂无运行记录，点左侧「运行」生成</p>
    <button
      v-for="h in history"
      :key="h.id"
      type="button"
      class="hist"
      :class="{ on: currentId === h.id }"
      :disabled="runBusy"
      @click="emit('open', h.id)"
    >
      <span>{{ h.condition }}</span>
      <span class="muted">{{ h.row_count }} 只 · {{ fmtDateTime(h.created_at) }}</span>
    </button>
    <PagerBar
      :page="page"
      :pages="pages"
      :total="total"
      :disabled="busy"
      @change="emit('page', $event)"
    />
  </div>
</template>

<style scoped>
.cfg-card {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: 0.75rem;
  box-shadow: var(--shadow-card);
  padding: 12px 14px;
  display: grid;
  gap: 10px;
  align-content: start;
}
.history-head {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.history-head strong {
  font-size: 0.875rem;
}
.tiny-btn {
  margin-left: auto;
  padding: 2px 8px;
  font-size: 0.75rem;
}
.hist {
  display: grid;
  gap: 2px;
  text-align: left;
  padding: 8px 10px;
  border: 1px solid var(--line);
  border-radius: 0.5rem;
  background: var(--surface-muted);
  cursor: pointer;
  font-size: 0.8125rem;
}
.hist:hover {
  border-color: var(--brand-soft);
}
.hist.on {
  border-color: var(--brand-soft);
  background: var(--brand-light);
  color: var(--brand-dark);
}
.err {
  margin: 0;
  color: var(--danger);
  font-size: 0.8125rem;
}
.muted {
  color: var(--ink-muted);
  font-size: 0.75rem;
}
</style>

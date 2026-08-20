<script setup lang="ts">
import type { WatchlistGroup } from '../../../api/watchlist'

defineProps<{
  checkedCount: number
  batchTargetGroupId: string
  otherGroups: WatchlistGroup[]
  groupId: string
}>()

const emit = defineEmits<{
  'update:batchTargetGroupId': [value: string]
  'batch-add': []
  'batch-remove': []
}>()
</script>

<template>
  <div class="batch-bar">
    <span class="muted batch-count">已选 {{ checkedCount }} 只</span>
    <label>
      目标组
      <select
        :value="batchTargetGroupId"
        @change="emit('update:batchTargetGroupId', ($event.target as HTMLSelectElement).value)"
      >
        <option value="">选择分组</option>
        <option v-for="g in otherGroups" :key="g.id" :value="g.id">{{ g.name }}</option>
      </select>
    </label>
    <button
      type="button"
      class="ghost"
      :disabled="!batchTargetGroupId"
      @click="emit('batch-add')"
    >
      批量加入
    </button>
    <button v-if="groupId" type="button" class="ghost" @click="emit('batch-remove')">
      批量移出此组
    </button>
  </div>
</template>

<style scoped>
.batch-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  padding: 8px 12px;
  border: 1px solid var(--line);
  border-radius: 0.75rem;
  background: var(--surface-muted);
}
.batch-bar label {
  display: flex;
  gap: 6px;
  align-items: center;
  font-size: 0.8rem;
  color: var(--muted);
}
select {
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: 0.5rem;
  color: var(--text);
  padding: 6px 10px;
}
.ghost {
  border-radius: 0.5rem;
  padding: 6px 10px;
  border: 1px solid var(--border);
  cursor: pointer;
  background: transparent;
  color: var(--text);
}
.ghost:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}
.batch-count {
  font-size: 0.85rem;
  white-space: nowrap;
}
.muted {
  color: var(--muted);
  font-size: 0.85rem;
}
</style>

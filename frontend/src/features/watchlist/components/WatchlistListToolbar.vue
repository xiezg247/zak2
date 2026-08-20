<script setup lang="ts">
type OptionalCol = 'industry' | 'turnover_rate' | 'amount'

defineProps<{
  addSymbol: string
  listFilter: string
  sortKey: string | null
  columnsOpen: boolean
  colVisible: Record<OptionalCol, boolean>
  displayedCount: number
}>()

const emit = defineEmits<{
  'update:addSymbol': [value: string]
  'update:listFilter': [value: string]
  'update:columnsOpen': [value: boolean]
  add: []
  'clear-sort': []
  'set-col-visible': [key: OptionalCol, on: boolean]
}>()

const optionalColLabels: { key: OptionalCol; label: string }[] = [
  { key: 'industry', label: '行业' },
  { key: 'turnover_rate', label: '换手%' },
  { key: 'amount', label: '成交额' },
]
</script>

<template>
  <div class="toolbar-block">
    <div class="toolbar">
      <div class="tabs">
        <input
          :value="addSymbol"
          placeholder="添加代码 600519.SSE"
          @input="emit('update:addSymbol', ($event.target as HTMLInputElement).value)"
          @keyup.enter="emit('add')"
        />
        <button type="button" class="primary" @click="emit('add')">添加</button>
        <input
          :value="listFilter"
          placeholder="过滤代码/名称"
          @input="emit('update:listFilter', ($event.target as HTMLInputElement).value)"
        />
        <button v-if="sortKey" type="button" class="ghost" @click="emit('clear-sort')">
          默认序
        </button>
        <button
          type="button"
          class="ghost"
          :class="{ on: columnsOpen }"
          @click="emit('update:columnsOpen', !columnsOpen)"
        >
          列
        </button>
      </div>
      <div class="actions">
        <span class="muted count-hint">{{ displayedCount }} 只</span>
      </div>
    </div>

    <div v-if="columnsOpen" class="col-prefs-panel">
      <label v-for="c in optionalColLabels" :key="c.key" class="col-pref-item">
        <input
          type="checkbox"
          :checked="colVisible[c.key]"
          @change="
            emit('set-col-visible', c.key, ($event.target as HTMLInputElement).checked)
          "
        />
        {{ c.label }}
      </label>
    </div>
  </div>
</template>

<style scoped>
.toolbar-block {
  display: grid;
  gap: 14px;
}
.toolbar {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
  flex-wrap: wrap;
}
.tabs,
.actions {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  align-items: center;
}
input {
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: 0.5rem;
  color: var(--text);
  padding: 6px 10px;
}
.tabs input {
  min-width: 150px;
}
.ghost,
.primary {
  border-radius: 0.5rem;
  padding: 6px 10px;
  border: 1px solid var(--border);
  cursor: pointer;
}
.ghost {
  background: transparent;
  color: var(--text);
}
.ghost.on {
  border-color: var(--brand, #333);
  color: var(--text);
  font-weight: 500;
}
.primary {
  background: var(--accent);
  border-color: transparent;
  color: var(--brand-foreground);
  font-weight: 600;
}
.count-hint {
  font-size: 0.8rem;
  font-variant-numeric: tabular-nums;
}
.col-prefs-panel {
  display: flex;
  flex-wrap: wrap;
  gap: 10px 14px;
  padding: 8px 12px;
  font-size: 0.85rem;
  color: var(--muted);
  background: var(--bg-elevated);
  border: 1px solid var(--line);
  border-radius: 0.75rem;
}
.col-pref-item {
  display: flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
}
.muted {
  color: var(--muted);
  font-size: 0.85rem;
}
</style>

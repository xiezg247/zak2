<script setup lang="ts">
const kind = defineModel<'industry' | 'concept'>('kind', { required: true })
const sort = defineModel<'net_flow_yi' | 'change_pct'>('sort', { required: true })
const tradeDate = defineModel<string>('tradeDate', { required: true })

defineProps<{
  dates: string[]
}>()
</script>

<template>
  <div class="toolbar">
    <div class="control-group">
      <span class="control-label">板块</span>
      <div class="tabs">
        <button type="button" :class="{ on: kind === 'concept' }" @click="kind = 'concept'">
          概念
        </button>
        <button type="button" :class="{ on: kind === 'industry' }" @click="kind = 'industry'">
          行业
        </button>
      </div>
    </div>
    <div class="control-group">
      <span class="control-label">排序</span>
      <div class="tabs">
        <button
          type="button"
          :class="{ on: sort === 'net_flow_yi' }"
          @click="sort = 'net_flow_yi'"
        >
          净流入
        </button>
        <button
          type="button"
          :class="{ on: sort === 'change_pct' }"
          @click="sort = 'change_pct'"
        >
          涨幅
        </button>
      </div>
    </div>
    <div class="control-group">
      <span class="control-label">日期</span>
      <select v-model="tradeDate">
        <option v-for="d in dates" :key="d" :value="d">{{ d }}</option>
      </select>
    </div>
    <RouterLink to="/market" class="cross-link toolbar-cross">← 市场</RouterLink>
  </div>
</template>

<style scoped>
.toolbar {
  display: flex;
  gap: 8px 20px;
  flex-wrap: wrap;
  align-items: center;
  padding: 12px 16px;
  border: 1px solid var(--line);
  border-radius: 0.75rem;
  background: var(--surface);
  box-shadow: var(--shadow-card);
}
.control-group {
  display: flex;
  align-items: center;
  gap: 8px;
}
.control-label {
  font-size: 0.75rem;
  color: var(--ink-faint);
  letter-spacing: 0.02em;
}
.tabs {
  display: flex;
  gap: 4px;
}
.tabs button {
  background: var(--surface);
  border: 1px solid var(--line);
  color: var(--ink-muted);
  border-radius: 0.5rem;
  padding: 6px 12px;
  font-size: 0.8125rem;
  transition:
    background 0.15s ease,
    color 0.15s ease,
    border-color 0.15s ease;
}
.tabs button:hover {
  color: var(--ink);
  border-color: var(--brand-soft);
}
.tabs button.on {
  background: var(--brand-light);
  color: var(--brand);
  border-color: var(--brand-soft);
  font-weight: 500;
}
select {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: 0.5rem;
  color: var(--ink);
  padding: 6px 10px;
  font-size: 0.8125rem;
}
.toolbar-cross {
  margin-left: auto;
}
.cross-link {
  color: var(--brand);
  text-decoration: none;
  font-size: 0.85rem;
  white-space: nowrap;
  align-self: center;
}
.cross-link:hover {
  text-decoration: underline;
}
</style>

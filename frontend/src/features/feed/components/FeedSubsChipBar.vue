<script setup lang="ts">
import type { FeedSub } from '../../../api/content'

defineProps<{
  subs: FeedSub[]
  subId: string
  loading: boolean
}>()

const emit = defineEmits<{
  'update:subId': [value: string]
  manage: []
}>()
</script>

<template>
  <section class="mid">
    <div class="side-title-row">
      <h2 class="side-title">我的订阅</h2>
      <span class="count muted">{{ subs.length }}</span>
      <span class="spacer"></span>
      <button type="button" class="ghost small" @click="emit('manage')">管理</button>
    </div>

    <div class="chip-flow">
      <button type="button" class="sub-chip" :class="{ on: !subId }" @click="emit('update:subId', '')">
        全部
      </button>
      <button
        v-for="s in subs"
        :key="s.id"
        type="button"
        class="sub-chip"
        :class="{ on: subId === s.id, off: !s.enabled }"
        :title="s.source_id"
        @click="emit('update:subId', s.id)"
      >
        {{ s.display_name || s.source_id }}
      </button>
    </div>

    <p v-if="!subs.length && !loading" class="muted tiny-text sub-hint">
      点击「管理」搜索关键词或填写 mid 添加订阅。
    </p>
  </section>
</template>

<style scoped>
.mid {
  grid-area: mid;
  min-height: 0;
  overflow: auto;
  border: 1px solid var(--line);
  border-radius: 0.9rem;
  background: var(--surface);
  box-shadow: var(--shadow-card);
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 12px;
  align-content: start;
}
.chip-flow {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.sub-chip {
  border: 1px solid var(--line);
  background: var(--surface);
  color: var(--ink);
  border-radius: 999px;
  padding: 3px 10px;
  font-size: 0.78rem;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  cursor: pointer;
  transition:
    border-color 0.15s ease,
    background 0.15s ease,
    color 0.15s ease;
}
.sub-chip:hover {
  border-color: var(--brand-soft);
  background: var(--brand-light);
}
.sub-chip.on {
  background: var(--brand);
  border-color: var(--brand);
  color: var(--brand-foreground);
}
.sub-chip.off {
  opacity: 0.55;
  text-decoration: line-through;
}
.spacer {
  flex: 1;
}
.ghost {
  border: 1px solid var(--line);
  background: var(--surface);
  color: var(--ink-muted);
  border-radius: 0.5rem;
  padding: 8px 12px;
  white-space: nowrap;
}
.ghost:hover:not(:disabled) {
  background: var(--brand-light);
  color: var(--brand);
  border-color: var(--brand-soft);
}
.ghost.small {
  padding: 4px 10px;
  font-size: 0.78rem;
}
.side-title {
  margin: 0;
  font-size: 0.72rem;
  font-weight: 600;
  letter-spacing: 0.08em;
  color: var(--ink-faint);
}
.side-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.count {
  font-size: 0.75rem;
}
.tiny-text {
  font-size: 0.72rem;
}
.sub-hint {
  margin: 0;
}

@media (max-width: 900px) {
  .mid {
    overflow: visible;
  }
}
</style>

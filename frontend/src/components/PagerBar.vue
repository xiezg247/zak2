<script setup lang="ts">
const props = defineProps<{
  page: number
  pages: number
  total?: number
  disabled?: boolean
}>()

const emit = defineEmits<{ (e: 'change', page: number): void }>()
</script>

<template>
  <div v-if="props.pages > 1" class="pager">
    <button
      type="button"
      class="pager-btn"
      :disabled="props.disabled || props.page <= 1"
      @click="emit('change', props.page - 1)"
    >
      上一页
    </button>
    <span class="pager-meta">
      {{ props.total != null ? `共 ${props.total} 条 · ` : '' }}第 {{ props.page }} / {{ props.pages }} 页
    </span>
    <button
      type="button"
      class="pager-btn"
      :disabled="props.disabled || props.page >= props.pages"
      @click="emit('change', props.page + 1)"
    >
      下一页
    </button>
  </div>
</template>

<style scoped>
.pager {
  display: flex;
  align-items: center;
  gap: 10px;
  justify-content: center;
  padding: 4px 0;
}
.pager-btn {
  background: var(--bg);
  border: 1px solid var(--border);
  color: var(--text);
  border-radius: 0.5rem;
  padding: 4px 10px;
  font-size: 0.8rem;
  cursor: pointer;
}
.pager-btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}
.pager-meta {
  color: var(--muted);
  font-size: 0.8rem;
}
</style>

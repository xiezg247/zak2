<script setup lang="ts">
import { computed, ref } from 'vue'
import type { WatchlistGroup } from '../../../api/watchlist'

const props = defineProps<{
  groups: WatchlistGroup[]
  groupId: string
  autoRefresh: boolean
  loading: boolean
  connected: boolean
}>()

const emit = defineEmits<{
  'update:autoRefresh': [value: boolean]
  select: [id: string]
  create: [name: string]
  rename: [id: string]
  delete: [id: string]
  move: [delta: -1 | 1]
  refresh: []
}>()

const newGroup = ref('')

const groupIndex = computed(() => {
  if (!props.groupId) return -1
  return props.groups.findIndex((g) => g.id === props.groupId)
})

function onCreate() {
  const name = newGroup.value.trim()
  if (!name) return
  emit('create', name)
  newGroup.value = ''
}
</script>

<template>
  <div class="group-bar">
    <div class="group-chips">
      <button
        type="button"
        class="group-chip"
        :class="{ on: !groupId }"
        @click="emit('select', '')"
      >
        全部自选
      </button>
      <span
        v-for="g in groups"
        :key="g.id"
        class="group-chip-wrap"
        :class="{ on: groupId === g.id }"
      >
        <button type="button" class="group-chip" @click="emit('select', g.id)">
          {{ g.name }}
        </button>
        <span class="group-chip-ops">
          <button
            type="button"
            class="chip-op"
            title="改名"
            @click.stop="emit('rename', g.id)"
          >
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
              stroke-linecap="round"
              stroke-linejoin="round"
            >
              <path
                d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z"
              />
            </svg>
          </button>
          <button
            type="button"
            class="chip-op danger"
            title="删除分组"
            @click.stop="emit('delete', g.id)"
          >
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
              stroke-linecap="round"
              stroke-linejoin="round"
            >
              <path
                d="M3 6h18M8 6V4a1 1 0 011-1h6a1 1 0 011 1v2m3 0v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6h14zM10 11v6M14 11v6"
              />
            </svg>
          </button>
        </span>
      </span>
      <span class="group-add">
        <input v-model="newGroup" placeholder="新分组名" @keyup.enter="onCreate" />
        <button type="button" class="ghost" @click="onCreate">建组</button>
      </span>
      <button
        v-if="groupId"
        type="button"
        class="ghost"
        :disabled="groupIndex <= 0"
        @click="emit('move', -1)"
      >
        上移
      </button>
      <button
        v-if="groupId"
        type="button"
        class="ghost"
        :disabled="groupIndex < 0 || groupIndex >= groups.length - 1"
        @click="emit('move', 1)"
      >
        下移
      </button>
    </div>
    <div class="actions">
      <label class="auto">
        <input
          type="checkbox"
          :checked="autoRefresh"
          @change="emit('update:autoRefresh', ($event.target as HTMLInputElement).checked)"
        />
        {{ connected ? 'WS 推送 + 慢轮询' : '每 15s 刷新行情' }}
      </label>
      <button type="button" class="ghost" :disabled="loading" @click="emit('refresh')">刷新</button>
    </div>
  </div>
</template>

<style scoped>
.group-bar {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
  flex-wrap: wrap;
  padding: 8px 10px;
  border: 1px solid var(--line);
  border-radius: 0.75rem;
  background: var(--surface);
  box-shadow: var(--shadow-card);
}
.group-chips {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  align-items: center;
}
.group-chip-wrap {
  position: relative;
  display: inline-flex;
  align-items: center;
  border: 1px solid var(--border);
  border-radius: 0.5rem;
  background: var(--bg);
  transition:
    border-color 0.15s,
    background 0.15s;
}
.group-chip {
  background: none;
  border: none;
  color: var(--text);
  padding: 5px 10px;
  font-size: 0.85rem;
  cursor: pointer;
  border-radius: inherit;
}
.group-chip:hover {
  color: var(--brand);
}
.group-chip-wrap.on {
  background: var(--brand-light);
  border-color: var(--brand-soft);
}
.group-chip-wrap.on .group-chip {
  color: var(--brand);
  font-weight: 600;
}
.group-chip-ops {
  display: none;
  align-items: center;
  gap: 1px;
  padding-right: 4px;
}
.group-chip-wrap:hover .group-chip-ops {
  display: inline-flex;
}
.group-chip-wrap:hover .group-chip {
  padding-right: 2px;
}
.chip-op {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: none;
  border: none;
  color: var(--muted);
  padding: 3px;
  border-radius: 0.3rem;
  cursor: pointer;
}
.chip-op:hover {
  color: var(--brand);
  background: var(--surface-muted);
}
.chip-op.danger:hover {
  color: var(--danger);
}
.chip-op svg {
  width: 12px;
  height: 12px;
}
.group-add {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.group-add input {
  min-width: 120px;
  padding: 5px 10px;
  font-size: 0.85rem;
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: 0.5rem;
  color: var(--text);
}
.actions {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  align-items: center;
}
.actions label.auto {
  white-space: nowrap;
}
.auto {
  display: flex;
  gap: 6px;
  align-items: center;
  color: var(--muted);
  font-size: 0.8rem;
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
</style>

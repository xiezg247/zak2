<script setup lang="ts">
import PagerBar from '../../../components/PagerBar.vue'
import type { Session } from '../../../api/ai'

defineProps<{
  sessions: Session[]
  sessionId: string
  page: number
  pages: number
  total: number
  includeContext: boolean
  useTools: boolean
}>()

const emit = defineEmits<{
  'update:includeContext': [v: boolean]
  'update:useTools': [v: boolean]
  newSession: []
  select: [id: string]
  remove: [id: string]
  page: [page: number]
}>()

function sessionTitle(s: { title: string }): string {
  const t = (s.title || '').trim()
  return t || '未命名对话'
}
</script>

<template>
  <aside class="left">
    <section class="side-section">
      <button class="primary block" type="button" @click="emit('newSession')">+ 新对话</button>
      <label class="check-label">
        <input
          type="checkbox"
          :checked="includeContext"
          @change="emit('update:includeContext', ($event.target as HTMLInputElement).checked)"
        />
        <span>注入自选/选股/回测上下文</span>
      </label>
      <label class="check-label">
        <input
          type="checkbox"
          :checked="useTools"
          @change="emit('update:useTools', ($event.target as HTMLInputElement).checked)"
        />
        <span>启用工具（Agent）</span>
      </label>
    </section>

    <section class="side-section grow">
      <h2 class="side-title">历史对话</h2>
      <p v-if="!sessions.length" class="hint muted">暂无会话，点上方新对话</p>
      <div class="sess-list">
        <button
          v-for="s in sessions"
          :key="s.id"
          type="button"
          class="sess"
          :class="{ on: sessionId === s.id }"
          @click="emit('select', s.id)"
        >
          <span class="sess-icon" aria-hidden="true">
            <svg viewBox="0 0 24 24" width="14" height="14">
              <path
                fill="none"
                stroke="currentColor"
                stroke-width="1.6"
                stroke-linecap="round"
                stroke-linejoin="round"
                d="M7.5 18.5 5 21V8.5A2.5 2.5 0 0 1 7.5 6h9A2.5 2.5 0 0 1 19 8.5v7a2.5 2.5 0 0 1-2.5 2.5H7.5Z"
              />
              <circle cx="9.5" cy="12" r="0.9" fill="currentColor" stroke="none" />
              <circle cx="12" cy="12" r="0.9" fill="currentColor" stroke="none" />
              <circle cx="14.5" cy="12" r="0.9" fill="currentColor" stroke="none" />
            </svg>
          </span>
          <span class="sess-title">{{ sessionTitle(s) }}</span>
          <span class="del" title="删除会话" @click.stop="emit('remove', s.id)">×</span>
        </button>
      </div>
      <PagerBar :page="page" :pages="pages" :total="total" @change="emit('page', $event)" />
    </section>
  </aside>
</template>

<style scoped>
.left {
  min-height: 0;
  border: 1px solid var(--line);
  border-radius: 0.9rem;
  background: var(--surface);
  box-shadow: var(--shadow-card);
  display: flex;
  flex-direction: column;
  padding: 12px;
  overflow: auto;
}
.side-section {
  display: grid;
  gap: 8px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--line-soft);
}
.side-section + .side-section {
  padding-top: 12px;
}
.side-section.grow {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
  border-bottom: none;
  padding-bottom: 0;
  padding-top: 12px;
  align-content: start;
}
.side-title {
  margin: 0;
  font-size: 0.78rem;
  font-weight: 400;
  letter-spacing: 0;
  color: var(--ink-faint);
}
.check-label {
  display: flex;
  align-items: center;
  gap: 7px;
  font-size: 0.8rem;
  color: var(--ink-muted);
  cursor: pointer;
  user-select: none;
}
.check-label input {
  accent-color: var(--brand);
}
.primary {
  background: var(--brand);
  border: none;
  color: var(--brand-foreground);
  border-radius: 0.5rem;
  padding: 9px 14px;
  font-weight: 500;
  white-space: nowrap;
}
.primary.block {
  width: 100%;
}
.hint {
  margin: 0;
  font-size: 0.75rem;
}
.muted {
  color: var(--muted);
}
.sess-list {
  flex: 1;
  min-height: 0;
  overflow: auto;
  display: grid;
  gap: 4px;
  align-content: start;
}
.sess {
  width: 100%;
  text-align: left;
  background: transparent;
  border: 1px solid transparent;
  border-radius: 0.5rem;
  color: var(--ink);
  padding: 8px 10px;
  display: grid;
  grid-template-columns: auto 1fr auto;
  gap: 8px;
  align-items: center;
  cursor: pointer;
}
.sess:hover {
  background: var(--surface-muted);
}
.sess.on {
  background: var(--brand-light);
  border-color: var(--brand-soft);
  color: var(--brand);
}
.sess-icon {
  display: inline-flex;
  color: var(--ink-faint);
}
.sess.on .sess-icon {
  color: var(--brand);
}
.sess-title {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 0.85rem;
}
.del {
  color: var(--muted);
  opacity: 0;
  font-size: 1rem;
  line-height: 1;
  padding: 0 2px;
}
.sess:hover .del {
  opacity: 1;
}
</style>

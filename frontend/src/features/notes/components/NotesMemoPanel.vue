<script setup lang="ts">
import PagerBar from '../../../components/PagerBar.vue'
import { fmtDateTime } from '../../../lib/format'
import type { NoteEntry } from '../../../api/content'

defineProps<{
  draftMemo: string
  draftEntry: string
  entries: NoteEntry[]
  entriesPage: number
  entriesPages: number
  entriesTotal: number
  saving: boolean
}>()

const emit = defineEmits<{
  'update:draftMemo': [value: string]
  'update:draftEntry': [value: string]
  save: []
  addEntry: []
  removeEntry: [id: number]
  pageChange: [page: number]
}>()
</script>

<template>
  <div class="memo-grid">
    <section class="panel memo-panel">
      <div class="panel-head">
        <h3>备忘</h3>
        <button class="primary" type="button" :disabled="saving" @click="emit('save')">
          {{ saving ? '保存中…' : '保存备忘' }}
        </button>
      </div>
      <textarea
        :value="draftMemo"
        rows="10"
        placeholder="记录这只股票的观察要点、交易计划…"
        @input="emit('update:draftMemo', ($event.target as HTMLTextAreaElement).value)"
      />
    </section>

    <section class="panel entries-panel">
      <div class="panel-head">
        <h3>
          流水 <span class="count muted">{{ entriesTotal }}</span>
        </h3>
      </div>
      <div class="add-row">
        <input
          :value="draftEntry"
          placeholder="追加一条流水"
          @input="emit('update:draftEntry', ($event.target as HTMLInputElement).value)"
          @keyup.enter="emit('addEntry')"
        />
        <button class="ghost" type="button" @click="emit('addEntry')">添加</button>
      </div>
      <div class="entry-list">
        <div v-if="!entries.length" class="empty muted">暂无流水记录</div>
        <div v-for="e in entries" :key="e.id" class="entry">
          <div class="entry-body">{{ e.body }}</div>
          <div class="entry-foot">
            <span class="muted mono">{{ fmtDateTime(e.created_at) }}</span>
            <button class="link" type="button" @click="emit('removeEntry', e.id)">删除</button>
          </div>
        </div>
      </div>
      <PagerBar
        :page="entriesPage"
        :pages="entriesPages"
        :total="entriesTotal"
        @change="emit('pageChange', $event)"
      />
    </section>
  </div>
</template>

<style scoped>
.memo-grid {
  display: grid;
  grid-template-columns: minmax(0, 5fr) minmax(0, 7fr);
  gap: 12px;
  flex: 1;
  min-height: 0;
}
.panel {
  border: 1px solid var(--line-soft);
  border-radius: 0.8rem;
  background: var(--surface);
  padding: 14px 16px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-height: 0;
}
.panel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-shrink: 0;
}
.panel-head h3 {
  margin: 0;
  font-size: 0.95rem;
  font-weight: 600;
  color: var(--ink);
}

textarea {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: 0.6rem;
  color: var(--ink);
  padding: 10px 12px;
  width: 100%;
  resize: vertical;
  font-size: 0.88rem;
  line-height: 1.6;
  min-height: 160px;
  flex: 1;
}
textarea:focus {
  border-color: var(--brand);
  box-shadow: 0 0 0 3px rgba(230, 100, 50, 0.15);
  outline: none;
}

.add-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 6px;
  flex-shrink: 0;
}
.add-row input {
  min-width: 0;
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: 0.5rem;
  color: var(--ink);
  padding: 8px 10px;
}
.entry-list {
  display: grid;
  gap: 8px;
  overflow: auto;
  flex: 1;
  align-content: start;
}
.entry {
  display: grid;
  gap: 6px;
  padding: 10px 12px;
  border: 1px solid var(--line-soft);
  border-radius: 0.6rem;
  background: var(--surface);
}
.entry-body {
  font-size: 0.88rem;
  color: var(--ink);
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
}
.entry-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
.link {
  background: none;
  border: none;
  color: var(--ink-faint);
  padding: 0;
  font-size: 0.78rem;
}
.link:hover {
  color: var(--danger);
}
.count {
  font-size: 0.75rem;
}
.empty {
  margin: 0;
  font-size: 0.85rem;
}

.primary {
  background: var(--brand);
  border: none;
  color: var(--brand-foreground);
  border-radius: 0.5rem;
  padding: 8px 12px;
  font-weight: 500;
  white-space: nowrap;
}
.primary:disabled {
  opacity: 0.55;
  cursor: not-allowed;
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

.mono {
  font-family: var(--mono);
}
.muted {
  color: var(--ink-muted);
  font-size: 0.8rem;
}

@media (max-width: 900px) {
  .memo-grid {
    grid-template-columns: 1fr;
  }
}
</style>

<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { useStockAnalysis } from '../composables/useStockAnalysis'
import { contentApi, type NoteMemo, type NoteEntry } from '../../../api/content'
import { fmtDateTime } from '../../../lib/format'

const analysis = useStockAnalysis()

const memo = ref<NoteMemo | null>(null)
const memoDraft = ref('')
const memoSaving = ref(false)
const memoErr = ref('')
const entries = ref<NoteEntry[]>([])
const entryDraft = ref('')
const entryErr = ref('')
const notesLoaded = ref(false)

async function loadNotes() {
  if (!analysis.vtSymbol.value || notesLoaded.value) return
  notesLoaded.value = true
  try {
    const vt = analysis.vtSymbol.value
    const [m, page] = await Promise.all([contentApi.memo(vt), contentApi.entriesPage(vt, 1, 50)])
    memo.value = m
    memoDraft.value = m.body || ''
    entries.value = page.items
  } catch (e) {
    memoErr.value = e instanceof Error ? e.message : '笔记加载失败'
  }
}

async function saveMemo() {
  if (!analysis.vtSymbol.value || memoSaving.value) return
  memoSaving.value = true
  memoErr.value = ''
  try {
    memo.value = await contentApi.saveMemo(analysis.vtSymbol.value, memoDraft.value.trim())
  } catch (e) {
    memoErr.value = e instanceof Error ? e.message : '速记保存失败'
  } finally {
    memoSaving.value = false
  }
}

async function addEntry() {
  const body = entryDraft.value.trim()
  if (!analysis.vtSymbol.value || !body) return
  entryErr.value = ''
  try {
    await contentApi.addEntry(analysis.vtSymbol.value, body)
    entryDraft.value = ''
    const page = await contentApi.entriesPage(analysis.vtSymbol.value, 1, 50)
    entries.value = page.items
  } catch (e) {
    entryErr.value = e instanceof Error ? e.message : '添加失败'
  }
}

async function removeEntry(id: number) {
  try {
    await contentApi.deleteEntry(id)
    entries.value = entries.value.filter((e) => e.id !== id)
  } catch (e) {
    entryErr.value = e instanceof Error ? e.message : '删除失败'
  }
}

function maybeLoad() {
  if (analysis.activeTab.value === 'notes' && analysis.vtSymbol.value && !notesLoaded.value) {
    void loadNotes()
  }
}

onMounted(() => maybeLoad())

watch(() => analysis.activeTab.value, () => maybeLoad())
</script>

<template>
  <div class="notes-tab">
    <section class="notes-card">
      <div class="block-head">
        <h4>速记</h4>
      </div>
      <textarea v-model="memoDraft" rows="3" placeholder="记录该标的要点…"></textarea>
      <button type="button" class="primary" :disabled="memoSaving" @click="saveMemo">
        {{ memoSaving ? '保存中…' : '保存速记' }}
      </button>
      <p v-if="memoErr" class="err">{{ memoErr }}</p>
    </section>
    <section class="notes-card">
      <div class="block-head">
        <h4>流水</h4>
      </div>
      <div class="entry-add">
        <input v-model="entryDraft" placeholder="追加一条流水" @keyup.enter="addEntry" />
        <button type="button" class="ghost" @click="addEntry">添加</button>
      </div>
      <p v-if="entryErr" class="err">{{ entryErr }}</p>
      <div v-if="entries.length" class="entry-list">
        <div v-for="e in entries" :key="e.id" class="entry">
          <div class="entry-body">{{ e.body }}</div>
          <div class="entry-foot">
            <span class="muted tiny">{{ fmtDateTime(e.created_at) }}</span>
            <button type="button" class="link" @click="removeEntry(e.id)">删</button>
          </div>
        </div>
      </div>
      <p v-else class="hint">暂无流水。</p>
    </section>
  </div>
</template>

<style scoped>
.muted {
  color: var(--muted);
}
.tiny {
  font-size: 0.72rem;
}
.err {
  margin: 0;
  color: var(--danger);
  font-size: 0.85rem;
}
.hint {
  margin: 4px 0;
  padding: 18px 12px;
  border: 1px dashed var(--line);
  border-radius: 0.6rem;
  background: var(--surface-muted);
  color: var(--muted);
  font-size: 0.82rem;
  text-align: center;
}
.block-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
.block-head h4 {
  margin: 0;
  font-size: 0.88rem;
  font-weight: 600;
  color: var(--ink);
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.block-head h4::before {
  content: '';
  width: 3px;
  height: 12px;
  border-radius: 2px;
  background: var(--brand);
}
.notes-tab {
  display: grid;
  gap: 12px;
}
.notes-card {
  display: grid;
  gap: 9px;
  border: 1px solid var(--line);
  border-radius: 0.75rem;
  background: var(--surface);
  padding: 14px 16px;
  box-shadow: var(--shadow-card);
}
.notes-card textarea {
  width: 100%;
  border: 1px solid var(--border);
  border-radius: 0.5rem;
  background: var(--bg-elevated);
  color: var(--text);
  padding: 9px 11px;
  resize: vertical;
  font-family: inherit;
  font-size: 0.85rem;
}
.entry-add {
  display: flex;
  gap: 8px;
}
.entry-add input {
  flex: 1;
  border: 1px solid var(--border);
  border-radius: 0.5rem;
  background: var(--bg-elevated);
  color: var(--text);
  padding: 8px 11px;
}
.primary {
  background: var(--accent);
  color: var(--brand-foreground);
  border: none;
  border-radius: 0.5rem;
  padding: 8px 14px;
  font-weight: 600;
  cursor: pointer;
  transition:
    background 0.15s ease,
    opacity 0.15s ease;
}
.primary:hover:not(:disabled) {
  background: var(--accent-hover);
}
.primary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.ghost {
  background: transparent;
  border: 1px solid var(--border);
  color: var(--text);
  border-radius: 0.5rem;
  padding: 7px 12px;
  cursor: pointer;
  transition:
    background 0.12s ease,
    color 0.12s ease,
    border-color 0.12s ease;
}
.ghost:hover {
  background: var(--brand-light);
  color: var(--brand);
  border-color: var(--brand-soft);
}
.entry-list {
  display: grid;
  gap: 5px;
}
.entry {
  border: 1px solid var(--border);
  border-radius: 0.5rem;
  padding: 8px 11px;
  background: var(--surface-muted);
  display: grid;
  gap: 4px;
}
.entry-body {
  font-size: 0.85rem;
}
.entry-foot {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.link {
  background: none;
  border: none;
  color: var(--muted);
  padding: 0;
  cursor: pointer;
}
.link:hover {
  color: var(--danger);
}
</style>

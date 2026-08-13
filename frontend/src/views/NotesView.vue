<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import AppShell from '../components/AppShell.vue'
import {
  contentApi,
  type NoteEntry,
  type NoteMemo,
  type NoteSymbol,
  type TeamReport,
  type TeamReportListItem,
} from '../api/content'

const route = useRoute()

const symbols = ref<NoteSymbol[]>([])
const selected = ref('')
const memo = ref<NoteMemo | null>(null)
const entries = ref<NoteEntry[]>([])
const reports = ref<TeamReportListItem[]>([])
const activeReport = ref<TeamReport | null>(null)
const draftMemo = ref('')
const draftEntry = ref('')
const newSymbol = ref('')
const error = ref('')
const saving = ref(false)
const tab = ref<'memo' | 'reports'>('memo')
const listFilter = ref('')
const loading = ref(false)

const displayedSymbols = computed(() => {
  const q = listFilter.value.trim().toLowerCase()
  if (!q) return symbols.value
  return symbols.value.filter((s) => {
    const vt = (s.vt_symbol || '').toLowerCase()
    const preview = (s.memo_preview || '').toLowerCase()
    return vt.includes(q) || preview.includes(q)
  })
})

async function loadSymbols() {
  symbols.value = await contentApi.noteSymbols()
  if (!selected.value && symbols.value.length) selected.value = symbols.value[0].vt_symbol
}

async function loadDetail() {
  if (!selected.value) {
    memo.value = null
    entries.value = []
    reports.value = []
    activeReport.value = null
    draftMemo.value = ''
    return
  }
  const [m, e, r] = await Promise.all([
    contentApi.memo(selected.value),
    contentApi.entries(selected.value),
    contentApi.teamReports(selected.value).catch(() => [] as TeamReportListItem[]),
  ])
  memo.value = m
  entries.value = e
  reports.value = r
  draftMemo.value = m.body

  const qReport = Number(route.query.report || 0)
  if (qReport) {
    tab.value = 'reports'
    await openReport(qReport)
  } else if (!reports.value.some((x) => x.id === activeReport.value?.id)) {
    activeReport.value = null
  }
}

async function openReport(id: number) {
  try {
    activeReport.value = await contentApi.teamReport(id)
    tab.value = 'reports'
  } catch (e) {
    error.value = e instanceof Error ? e.message : '打开研报失败'
  }
}

async function saveMemo() {
  if (!selected.value) return
  saving.value = true
  error.value = ''
  try {
    memo.value = await contentApi.saveMemo(selected.value, draftMemo.value)
    await loadSymbols()
  } catch (e) {
    error.value = e instanceof Error ? e.message : '保存失败'
  } finally {
    saving.value = false
  }
}

async function addEntry() {
  if (!selected.value || !draftEntry.value.trim()) return
  try {
    await contentApi.addEntry(selected.value, draftEntry.value.trim())
    draftEntry.value = ''
    await loadDetail()
    await loadSymbols()
  } catch (e) {
    error.value = e instanceof Error ? e.message : '添加失败'
  }
}

async function removeEntry(id: number) {
  await contentApi.deleteEntry(id)
  await loadDetail()
  await loadSymbols()
}

async function openOrCreate() {
  const vt = newSymbol.value.trim()
  if (!vt) return
  selected.value = vt.includes('.') ? vt : `${vt}.SSE`
  newSymbol.value = ''
  await loadDetail()
}

watch(selected, () => {
  void loadDetail()
})

onMounted(async () => {
  loading.value = true
  error.value = ''
  try {
    const qSym = String(route.query.symbol || '').trim()
    if (qSym) selected.value = qSym
    await loadSymbols()
    await loadDetail()
  } catch (e) {
    error.value = e instanceof Error ? e.message : '加载失败'
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <AppShell title="笔记" subtitle="备忘 · 流水 · 研报" active="notes">
    <div class="page">
      <p v-if="error" class="err">{{ error }}</p>
      <div class="workspace">
        <aside class="left">
          <div class="row">
            <input v-model="newSymbol" placeholder="600519.SSE" @keyup.enter="openOrCreate" />
            <button class="primary" type="button" @click="openOrCreate">打开</button>
          </div>
          <input
            v-if="symbols.length"
            v-model="listFilter"
            class="filter"
            placeholder="过滤代码/备忘"
          />
          <p v-if="loading" class="empty muted">加载中…</p>
          <template v-else>
            <p v-if="!symbols.length" class="hint muted">输入代码打开笔记</p>
            <p v-else-if="!displayedSymbols.length" class="empty muted">无匹配标的</p>
            <button
              v-for="s in displayedSymbols"
              :key="s.vt_symbol"
              type="button"
              class="sym"
              :class="{ on: selected === s.vt_symbol }"
              @click="selected = s.vt_symbol"
            >
              <span class="mono">{{ s.vt_symbol }}</span>
              <span class="muted">流水 {{ s.entry_count }}</span>
              <span class="preview muted">{{ s.memo_preview || '无备忘' }}</span>
            </button>
          </template>
        </aside>
        <section v-if="selected" class="right">
          <h2 class="mono">{{ selected }}</h2>
          <div class="tabs">
            <button type="button" :class="{ on: tab === 'memo' }" @click="tab = 'memo'">备忘/流水</button>
            <button type="button" :class="{ on: tab === 'reports' }" @click="tab = 'reports'">研报</button>
          </div>

          <template v-if="tab === 'memo'">
            <label>
              备忘
              <textarea v-model="draftMemo" rows="8" />
            </label>
            <button class="primary" type="button" :disabled="saving" @click="saveMemo">保存备忘</button>

            <h3>流水</h3>
            <div class="row">
              <input v-model="draftEntry" placeholder="追加一条流水" @keyup.enter="addEntry" />
              <button class="ghost" type="button" @click="addEntry">添加</button>
            </div>
            <div class="entry" v-for="e in entries" :key="e.id">
              <div class="meta muted">{{ e.created_at }}</div>
              <div>{{ e.body }}</div>
              <button class="link" type="button" @click="removeEntry(e.id)">删</button>
            </div>
          </template>

          <template v-else>
            <p v-if="!reports.length" class="muted">暂无研报。在 AI 页跑投研团队后会自动生成。</p>
            <button
              v-for="r in reports"
              :key="r.id"
              type="button"
              class="report-item"
              :class="{ on: activeReport?.id === r.id }"
              @click="openReport(r.id)"
            >
              <div class="report-title">{{ r.title }}</div>
              <div class="muted tiny">{{ r.created_at }} · {{ r.mode }}</div>
              <div class="preview muted">{{ r.summary }}</div>
            </button>
            <article v-if="activeReport" class="report-body">
              <h3>{{ activeReport.title }}</h3>
              <pre>{{ activeReport.body }}</pre>
            </article>
          </template>
        </section>
        <section v-else class="right muted">
          <template v-if="loading">加载中…</template>
          <template v-else-if="!symbols.length">暂无笔记标的</template>
          <template v-else>选择或打开一只股票</template>
        </section>
      </div>
    </div>
  </AppShell>
</template>

<style scoped>
.page {
  height: 100%;
  padding: 0;
}
.err {
  color: var(--danger);
}
.workspace {
  display: grid;
  grid-template-columns: 280px 1fr;
  gap: 12px;
  height: calc(100% - 8px);
}
.left,
.right {
  border: 1px solid var(--border);
  border-radius: 0.75rem;
  background: var(--bg-elevated);
  padding: 12px;
  overflow: auto;
  display: grid;
  gap: 8px;
  align-content: start;
}
.row {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 8px;
}
.filter {
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 0.5rem;
  color: var(--text);
  padding: 8px 10px;
  width: 100%;
}
.empty,
.hint {
  margin: 4px 0 0;
  font-size: 0.85rem;
}
.tabs {
  display: flex;
  gap: 8px;
}
.tabs button {
  background: transparent;
  border: 1px solid var(--border);
  color: var(--text);
  border-radius: 0.5rem;
  padding: 6px 10px;
}
.tabs button.on {
  background: var(--brand-light);
  color: var(--brand);
  border-color: var(--brand-soft);
  font-weight: 500;
}
input,
textarea {
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 0.5rem;
  color: var(--text);
  padding: 8px 10px;
  width: 100%;
}
.sym,
.report-item {
  text-align: left;
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 0.5rem;
  color: var(--text);
  padding: 8px;
  display: grid;
  gap: 2px;
}
.sym.on,
.report-item.on {
  border-color: var(--accent);
}
.preview {
  font-size: 0.8rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.tiny {
  font-size: 0.75rem;
}
.report-title {
  font-weight: 600;
}
.report-body {
  border-top: 1px solid var(--border);
  padding-top: 10px;
  display: grid;
  gap: 8px;
}
.report-body pre {
  white-space: pre-wrap;
  margin: 0;
  font-family: inherit;
  font-size: 0.9rem;
  line-height: 1.5;
}
.primary {
  background: var(--accent);
  border: none;
  color: var(--brand-foreground);
  border-radius: 0.5rem;
  padding: 8px 12px;
}
.ghost {
  background: transparent;
  border: 1px solid var(--border);
  color: var(--text);
  border-radius: 0.5rem;
  padding: 8px 12px;
}
.link {
  background: none;
  border: none;
  color: var(--muted);
  padding: 0;
  justify-self: start;
}
.entry {
  border-top: 1px solid var(--border);
  padding-top: 8px;
  display: grid;
  gap: 4px;
}
.mono {
  font-family: var(--mono);
}
.muted {
  color: var(--muted);
  font-size: 0.85rem;
}
h2,
h3 {
  margin: 0;
}
label {
  display: grid;
  gap: 6px;
  color: var(--muted);
  font-size: 0.85rem;
}
@media (max-width: 900px) {
  .workspace {
    grid-template-columns: 1fr;
  }
}
</style>

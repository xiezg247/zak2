<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import AppShell from '../../../components/AppShell.vue'
import { confirmDialog } from '../../../lib/dialog'
import {
  contentApi,
  type NoteEntry,
  type NoteMemo,
  type NoteSymbol,
  type TeamReport,
  type TeamReportListItem,
} from '../../../api/content'
import NotesTopBar from '../components/NotesTopBar.vue'
import NotesMemoPanel from '../components/NotesMemoPanel.vue'
import NotesReportsPanel from '../components/NotesReportsPanel.vue'

const route = useRoute()

const symbols = ref<NoteSymbol[]>([])
const selected = ref('')
const memo = ref<NoteMemo | null>(null)
const entries = ref<NoteEntry[]>([])
const reports = ref<TeamReportListItem[]>([])
const entriesPage = ref(1)
const entriesPages = ref(0)
const entriesTotal = ref(0)
const reportsPage = ref(1)
const reportsPages = ref(0)
const reportsTotal = ref(0)
const activeReport = ref<TeamReport | null>(null)
const draftMemo = ref('')
const draftEntry = ref('')
const error = ref('')
const saving = ref(false)
const tab = ref<'memo' | 'reports'>('memo')
const listFilter = ref('')
const reportFilter = ref('')
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

const displayedReports = computed(() => {
  const q = reportFilter.value.trim().toLowerCase()
  if (!q) return reports.value
  return reports.value.filter((r) => {
    const t = (r.title || '').toLowerCase()
    const s = (r.summary || '').toLowerCase()
    return t.includes(q) || s.includes(q)
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
    entriesTotal.value = 0
    entriesPages.value = 0
    reportsTotal.value = 0
    reportsPages.value = 0
    activeReport.value = null
    draftMemo.value = ''
    return
  }
  const m = await contentApi.memo(selected.value)
  memo.value = m
  draftMemo.value = m.body
  entriesPage.value = 1
  reportsPage.value = 1
  await Promise.all([loadEntries(), loadReports()])

  const qReport = Number(route.query.report || 0)
  if (qReport) {
    tab.value = 'reports'
    await openReport(qReport)
  } else if (!reports.value.some((x) => x.id === activeReport.value?.id)) {
    activeReport.value = null
  }
}

async function loadEntries() {
  if (!selected.value) {
    entries.value = []
    entriesTotal.value = 0
    entriesPages.value = 0
    return
  }
  const p = await contentApi.entriesPage(selected.value, entriesPage.value, 50)
  entries.value = p.items
  entriesTotal.value = p.total
  entriesPages.value = p.pages
}

async function loadReports() {
  if (!selected.value) {
    reports.value = []
    reportsTotal.value = 0
    reportsPages.value = 0
    return
  }
  try {
    const p = await contentApi.teamReportsPage(selected.value, reportsPage.value, 20)
    reports.value = p.items
    reportsTotal.value = p.total
    reportsPages.value = p.pages
  } catch {
    reports.value = []
    reportsTotal.value = 0
    reportsPages.value = 0
  }
}

async function goEntriesPage(p: number) {
  entriesPage.value = p
  await loadEntries()
}

async function goReportsPage(p: number) {
  reportsPage.value = p
  await loadReports()
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
  const ok = await confirmDialog({
    title: '删除流水',
    message: '确定删除这条流水？',
    danger: true,
  })
  if (!ok) return
  await contentApi.deleteEntry(id)
  await loadDetail()
  await loadSymbols()
}

async function openOrCreate(vtRaw: string) {
  const vt = vtRaw.trim()
  if (!vt) return
  selected.value = vt.includes('.') ? vt : `${vt}.SSE`
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

      <NotesTopBar
        :symbols="symbols"
        :displayed-symbols="displayedSymbols"
        :selected="selected"
        v-model:list-filter="listFilter"
        :loading="loading"
        @select="selected = $event"
        @open="openOrCreate"
      />

      <section v-if="selected" class="content">
        <header class="detail-head">
          <h2 class="mono">{{ selected }}</h2>
          <div class="tabs">
            <button type="button" :class="{ on: tab === 'memo' }" @click="tab = 'memo'">
              备忘 / 流水
            </button>
            <button type="button" :class="{ on: tab === 'reports' }" @click="tab = 'reports'">
              研报
            </button>
          </div>
        </header>

        <NotesMemoPanel
          v-if="tab === 'memo'"
          v-model:draft-memo="draftMemo"
          v-model:draft-entry="draftEntry"
          :entries="entries"
          :entries-page="entriesPage"
          :entries-pages="entriesPages"
          :entries-total="entriesTotal"
          :saving="saving"
          @save="saveMemo"
          @add-entry="addEntry"
          @remove-entry="removeEntry"
          @page-change="goEntriesPage"
        />

        <NotesReportsPanel
          v-else
          :selected="selected"
          :reports="reports"
          :displayed-reports="displayedReports"
          v-model:report-filter="reportFilter"
          :active-report="activeReport"
          :reports-page="reportsPage"
          :reports-pages="reportsPages"
          :reports-total="reportsTotal"
          @open-report="openReport"
          @page-change="goReportsPage"
        />
      </section>

      <section v-else class="content empty-state muted">
        <template v-if="loading">加载中…</template>
        <template v-else-if="!symbols.length">暂无笔记标的</template>
        <template v-else>选择或打开一只股票</template>
      </section>
    </div>
  </AppShell>
</template>

<style scoped>
.page {
  display: flex;
  flex-direction: column;
  gap: 12px;
  height: 100%;
  padding: 16px 24px 24px;
}
.err {
  margin: 0;
  color: var(--danger);
  font-size: 0.85rem;
}

.content {
  border: 1px solid var(--line);
  border-radius: 0.9rem;
  background: var(--surface);
  box-shadow: var(--shadow-card);
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 16px;
  overflow: auto;
}
.detail-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  flex-shrink: 0;
}
.detail-head h2 {
  margin: 0;
  font-size: 1.15rem;
  font-weight: 600;
  color: var(--ink);
}
.tabs {
  display: flex;
  gap: 4px;
  background: var(--surface-muted);
  border-radius: 0.6rem;
  padding: 3px;
}
.tabs button {
  background: transparent;
  border: none;
  color: var(--ink-muted);
  border-radius: 0.45rem;
  padding: 6px 12px;
  font-size: 0.82rem;
  transition:
    background 0.15s ease,
    color 0.15s ease;
}
.tabs button.on {
  background: var(--surface);
  color: var(--brand);
  font-weight: 500;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);
}

.empty-state {
  display: grid;
  place-items: center;
  color: var(--ink-muted);
  font-size: 0.9rem;
  padding: 40px;
}

.mono {
  font-family: var(--mono);
}
.muted {
  color: var(--ink-muted);
  font-size: 0.8rem;
}

@media (max-width: 900px) {
  .content {
    overflow: visible;
  }
}
</style>

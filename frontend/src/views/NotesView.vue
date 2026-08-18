<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import AppShell from '../components/AppShell.vue'
import MarkdownView from '../components/MarkdownView.vue'
import PagerBar from '../components/PagerBar.vue'
import { confirmDialog } from '../lib/dialog'
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
const entriesPage = ref(1)
const entriesPages = ref(0)
const entriesTotal = ref(0)
const reportsPage = ref(1)
const reportsPages = ref(0)
const reportsTotal = ref(0)
const activeReport = ref<TeamReport | null>(null)
const draftMemo = ref('')
const draftEntry = ref('')
const newSymbol = ref('')
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

      <section class="topbar">
        <div class="topbar-head">
          <div class="open-group">
            <input
              v-model="newSymbol"
              placeholder="600519.SSE"
              @keyup.enter="openOrCreate"
            />
            <button class="primary" type="button" @click="openOrCreate">打开</button>
          </div>
          <input
            v-if="symbols.length"
            v-model="listFilter"
            class="filter"
            placeholder="过滤代码 / 备忘"
          />
          <span class="count muted">{{ symbols.length }} 个标的</span>
        </div>

        <div class="sym-strip">
          <button
            v-for="s in displayedSymbols"
            :key="s.vt_symbol"
            type="button"
            class="sym"
            :class="{ on: selected === s.vt_symbol }"
            :title="s.memo_preview || '无备忘'"
            @click="selected = s.vt_symbol"
          >
            <span class="mono">{{ s.vt_symbol }}</span>
            <span class="badge">{{ s.entry_count }}</span>
          </button>
          <p v-if="loading" class="empty muted">加载中…</p>
          <p v-else-if="!symbols.length" class="hint muted">输入代码打开笔记</p>
          <p v-else-if="!displayedSymbols.length" class="empty muted">无匹配标的</p>
        </div>
      </section>

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

        <template v-if="tab === 'memo'">
          <div class="memo-grid">
            <section class="panel memo-panel">
              <div class="panel-head">
                <h3>备忘</h3>
                <button class="primary" type="button" :disabled="saving" @click="saveMemo">
                  {{ saving ? '保存中…' : '保存备忘' }}
                </button>
              </div>
              <textarea
                v-model="draftMemo"
                rows="10"
                placeholder="记录这只股票的观察要点、交易计划…"
              />
            </section>

            <section class="panel entries-panel">
              <div class="panel-head">
                <h3>流水 <span class="count muted">{{ entriesTotal }}</span></h3>
              </div>
              <div class="add-row">
                <input v-model="draftEntry" placeholder="追加一条流水" @keyup.enter="addEntry" />
                <button class="ghost" type="button" @click="addEntry">添加</button>
              </div>
              <div class="entry-list">
                <div v-if="!entries.length" class="empty muted">暂无流水记录</div>
                <div v-for="e in entries" :key="e.id" class="entry">
                  <div class="entry-body">{{ e.body }}</div>
                  <div class="entry-foot">
                    <span class="muted mono">{{ e.created_at }}</span>
                    <button class="link" type="button" @click="removeEntry(e.id)">删除</button>
                  </div>
                </div>
              </div>
              <PagerBar
                :page="entriesPage"
                :pages="entriesPages"
                :total="entriesTotal"
                @change="goEntriesPage"
              />
            </section>
          </div>
        </template>

        <template v-else>
          <div class="reports-grid">
            <section class="panel reports-panel">
              <div class="panel-head">
                <h3>研报 <span class="count muted">{{ reportsTotal }}</span></h3>
              </div>
              <p v-if="!reports.length" class="empty muted">
                暂无研报。
                <RouterLink :to="{ path: '/ai', query: { symbol: selected } }" class="link">
                  去 AI 跑投研团队
                </RouterLink>
              </p>
              <template v-else>
                <input v-model="reportFilter" class="filter" placeholder="过滤标题 / 摘要" />
                <p v-if="!displayedReports.length" class="empty muted">无匹配研报</p>
                <div class="report-list">
                  <button
                    v-for="r in displayedReports"
                    :key="r.id"
                    type="button"
                    class="report-item"
                    :class="{ on: activeReport?.id === r.id }"
                    @click="openReport(r.id)"
                  >
                    <div class="report-title">{{ r.title }}</div>
                    <div class="report-meta muted">{{ r.created_at }} · {{ r.mode }}</div>
                    <div class="report-summary muted">{{ r.summary }}</div>
                  </button>
                </div>
                <PagerBar
                  :page="reportsPage"
                  :pages="reportsPages"
                  :total="reportsTotal"
                  @change="goReportsPage"
                />
              </template>
            </section>

            <article v-if="activeReport" class="panel report-body">
              <h3>{{ activeReport.title }}</h3>
              <MarkdownView :source="activeReport.body" />
            </article>
            <div v-else class="panel report-body empty-state muted">选择一份研报查看详情</div>
          </div>
        </template>
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

/* ---------- 顶部标的条 ---------- */
.topbar,
.content {
  border: 1px solid var(--line);
  border-radius: 0.9rem;
  background: var(--surface);
  box-shadow: var(--shadow-card);
}
.topbar {
  padding: 12px 14px;
  display: grid;
  gap: 10px;
}
.topbar-head {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
.open-group {
  display: grid;
  grid-template-columns: 220px auto;
  gap: 6px;
}
.open-group input {
  min-width: 0;
  background: var(--surface);
  border: 1px solid var(--line);
  color: var(--ink);
  border-radius: 0.5rem;
  padding: 8px 10px;
}
.filter {
  flex: 1;
  min-width: 160px;
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: 0.5rem;
  color: var(--ink);
  padding: 8px 10px;
}
.count {
  font-size: 0.75rem;
}

.sym-strip {
  display: flex;
  align-items: center;
  gap: 6px;
  overflow-x: auto;
  padding-bottom: 2px;
}
.sym {
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: 999px;
  color: var(--ink);
  padding: 5px 12px;
  font-size: 0.82rem;
  transition:
    background 0.15s ease,
    border-color 0.15s ease,
    color 0.15s ease;
}
.sym:hover {
  border-color: var(--brand-soft);
  background: var(--surface-muted);
}
.sym.on {
  background: var(--brand);
  border-color: var(--brand);
  color: var(--brand-foreground);
}
.sym.on .badge {
  background: var(--brand-foreground);
  color: var(--brand);
  border-color: transparent;
}
.badge {
  font-size: 0.7rem;
  background: var(--brand-light);
  color: var(--brand-dark);
  border: 1px solid var(--brand-soft);
  border-radius: 999px;
  padding: 0 7px;
  line-height: 1.5;
}
.hint,
.empty {
  margin: 0;
  font-size: 0.85rem;
}

/* ---------- 内容区 ---------- */
.content {
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

/* ---------- 备忘 / 流水 ---------- */
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

/* ---------- 研报 ---------- */
.reports-grid {
  display: grid;
  grid-template-columns: 320px minmax(0, 1fr);
  gap: 12px;
  flex: 1;
  min-height: 0;
}
.reports-panel {
  overflow: auto;
}
.report-list {
  display: grid;
  gap: 6px;
  overflow: auto;
  flex: 1;
  align-content: start;
}
.report-item {
  text-align: left;
  background: var(--surface);
  border: 1px solid var(--line-soft);
  border-radius: 0.6rem;
  color: var(--ink);
  padding: 10px 12px;
  display: grid;
  gap: 4px;
  transition:
    border-color 0.15s ease,
    background 0.15s ease;
}
.report-item:hover {
  border-color: var(--brand-soft);
  background: var(--surface-muted);
}
.report-item.on {
  border-color: var(--brand);
  background: var(--brand-light);
}
.report-title {
  font-weight: 600;
  font-size: 0.9rem;
}
.report-meta {
  font-size: 0.75rem;
}
.report-summary {
  font-size: 0.8rem;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.report-body {
  overflow: auto;
  align-content: start;
}
.report-body h3 {
  margin: 0 0 8px;
  font-size: 1.05rem;
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
  .memo-grid,
  .reports-grid {
    grid-template-columns: 1fr;
  }
  .content {
    overflow: visible;
  }
}
</style>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useStockAnalysis, type AnalysisTabKey } from '../composables/useStockAnalysis'
import { marketApi } from '../../../api/market'
import { opsApi } from '../../../api/ops'
import AnalysisQuotePanel from './AnalysisQuotePanel.vue'
import AnalysisFundPanel from './AnalysisFundPanel.vue'
import AnalysisAiPanel from './AnalysisAiPanel.vue'
import AnalysisNotesPanel from './AnalysisNotesPanel.vue'

const analysis = useStockAnalysis()

const TABS: { key: AnalysisTabKey; label: string }[] = [
  { key: 'quote', label: '行情' },
  { key: 'fundamental', label: '基本面' },
  { key: 'radar', label: '雷达' },
  { key: 'ai', label: 'AI研报' },
  { key: 'notes', label: '笔记' },
]

const displayName = computed(() => analysis.name.value || analysis.vtSymbol.value || '—')

function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape' && analysis.isOpen.value) analysis.close()
}

function switchTab(tab: AnalysisTabKey) {
  analysis.activeTab.value = tab
}

const radarEntry = ref<{
  card_count: number
  card_titles: string[]
  resonance_score: number
  seal_time_label?: string
} | null>(null)
const radarErr = ref('')
const radarLoading = ref(false)

async function loadRadar() {
  if (!analysis.vtSymbol.value || analysis.isLoaded('radar')) return
  radarLoading.value = true
  radarErr.value = ''
  try {
    const vt = analysis.vtSymbol.value
    const resp = await marketApi.radarResonance({ top_n: 100, min_cards: 1 })
    radarEntry.value = resp.entries.find((e) => e.vt_symbol === vt) || null
    analysis.markLoaded('radar')
  } catch (e) {
    radarErr.value = e instanceof Error ? e.message : '雷达共振加载失败'
  } finally {
    radarLoading.value = false
  }
}

watch(
  () => analysis.activeTab.value,
  (tab) => {
    if (tab === 'radar' && analysis.vtSymbol.value && !analysis.isLoaded('radar')) void loadRadar()
  },
)

const SYNC_JOBS = [
  { id: 'sync_watchlist_financials', label: '同步财报', tab: 'fundamental' },
  { id: 'sync_disclosure_calendar', label: '同步披露计划', tab: 'fundamental' },
  { id: 'fill_watchlist_bars', label: '补全日 K', tab: 'quote' },
] as const

const syncMenuOpen = ref(false)
const syncBusy = ref('')
const syncMsg = ref('')
const syncErr = ref('')

function closeSyncMenu() {
  syncMenuOpen.value = false
}

async function runSyncJob(jobId: string, tab: (typeof SYNC_JOBS)[number]['tab']) {
  if (syncBusy.value) return
  syncBusy.value = jobId
  syncMsg.value = ''
  syncErr.value = ''
  closeSyncMenu()
  try {
    const accepted = await opsApi.runJob(jobId)
    analysis.invalidate(tab)
    syncMsg.value = `已提交 ${accepted.kind}（${accepted.job_id}），稍后切回该页签即可看到更新。`
  } catch (e) {
    syncErr.value = e instanceof Error ? e.message : '提交同步任务失败'
  } finally {
    syncBusy.value = ''
  }
}

watch(
  () => analysis.vtSymbol.value,
  () => {
    syncMsg.value = ''
    syncErr.value = ''
    syncMenuOpen.value = false
    syncBusy.value = ''
  },
)

onMounted(() => {
  window.addEventListener('keydown', onKeydown)
})

onUnmounted(() => {
  window.removeEventListener('keydown', onKeydown)
})
</script>

<template>
  <Teleport to="body">
    <transition name="stock">
      <div v-if="analysis.isOpen.value" class="stock-overlay" @click.self="analysis.close()">
        <div
          class="stock-modal"
          role="dialog"
          aria-modal="true"
          aria-label="个股分析"
          @click.self="closeSyncMenu"
        >
          <div class="stock-head">
            <strong class="stock-title">{{ displayName }}</strong>
            <span class="stock-code mono">{{ analysis.vtSymbol.value }}</span>
            <div class="spacer"></div>
            <div class="sync-menu">
              <button
                type="button"
                class="icon-btn"
                :class="{ on: syncMenuOpen }"
                title="数据同步（Ops 任务）"
                :disabled="!!syncBusy"
                @click="syncMenuOpen = !syncMenuOpen"
              >
                <svg
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="2"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                >
                  <path d="M21 12a9 9 0 1 1-2.64-6.36" />
                  <path d="M21 3v6h-6" />
                </svg>
              </button>
              <div v-if="syncMenuOpen" class="sync-pop">
                <button
                  v-for="j in SYNC_JOBS"
                  :key="j.id"
                  type="button"
                  class="sync-item"
                  :disabled="syncBusy === j.id"
                  @click="runSyncJob(j.id, j.tab)"
                >
                  {{ syncBusy === j.id ? '提交中…' : j.label }}
                </button>
              </div>
            </div>
            <button type="button" class="icon-btn" title="关闭" @click="analysis.close()">
              <svg
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="2"
                stroke-linecap="round"
                stroke-linejoin="round"
              >
                <path d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          <div class="stock-tabs">
            <button
              v-for="t in TABS"
              :key="t.key"
              type="button"
              :class="{ on: analysis.activeTab.value === t.key }"
              @click="switchTab(t.key)"
            >
              {{ t.label }}
            </button>
          </div>

          <div v-if="syncMsg" class="sync-banner ok">{{ syncMsg }}</div>
          <div v-if="syncErr" class="sync-banner err">{{ syncErr }}</div>

          <div class="stock-body">
            <AnalysisQuotePanel v-show="analysis.activeTab.value === 'quote'" />
            <AnalysisFundPanel v-show="analysis.activeTab.value === 'fundamental'" />

            <div v-show="analysis.activeTab.value === 'radar'" class="radar-tab">
              <p v-if="radarLoading" class="hint">加载雷达共振…</p>
              <p v-else-if="radarErr" class="err">{{ radarErr }}</p>
              <template v-else-if="radarEntry">
                <div class="radar-summary">
                  <div class="q-item">
                    <span class="q-label">共振分</span>
                    <span class="q-value">{{ radarEntry.resonance_score.toFixed(1) }}</span>
                  </div>
                  <div class="q-item">
                    <span class="q-label">卡片数</span>
                    <span class="q-value">{{ radarEntry.card_count }}</span>
                  </div>
                  <div v-if="radarEntry.seal_time_label" class="q-item">
                    <span class="q-label">封板</span>
                    <span class="q-value">{{ radarEntry.seal_time_label }}</span>
                  </div>
                </div>
                <div v-if="radarEntry.card_titles.length" class="card-titles">
                  <span v-for="t in radarEntry.card_titles" :key="t" class="chip-tag">{{ t }}</span>
                </div>
                <p v-else class="hint">暂无卡片标题</p>
              </template>
              <p v-else class="hint">暂无共振</p>
            </div>

            <AnalysisAiPanel v-show="analysis.activeTab.value === 'ai'" />
            <AnalysisNotesPanel v-show="analysis.activeTab.value === 'notes'" />
          </div>
        </div>
      </div>
    </transition>
  </Teleport>
</template>

<style scoped>
/* ---------- 遮罩与弹窗骨架 ---------- */
.stock-overlay {
  position: fixed;
  inset: 0;
  z-index: 1000;
  display: grid;
  place-items: center;
  background: rgba(15, 15, 15, 0.42);
  backdrop-filter: blur(3px);
  -webkit-backdrop-filter: blur(3px);
  padding: 24px;
}
.stock-enter-active,
.stock-leave-active {
  transition:
    opacity 0.22s ease,
    transform 0.22s ease;
}
.stock-enter-from,
.stock-leave-to {
  opacity: 0;
}
.stock-enter-from .stock-modal,
.stock-leave-to .stock-modal {
  transform: translateY(10px) scale(0.98);
}
.stock-modal {
  width: 100%;
  max-width: 920px;
  max-height: 88vh;
  display: grid;
  grid-template-rows: auto auto auto 1fr;
  gap: 12px;
  padding: 18px 20px;
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: 1rem;
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.16);
}

/* ---------- 头部 ---------- */
.stock-head {
  display: flex;
  align-items: center;
  gap: 10px;
}
.stock-title {
  font-size: 1.08rem;
  font-weight: 700;
  color: var(--ink);
  letter-spacing: 0.01em;
}
.stock-code {
  font-size: 0.76rem;
  color: var(--brand);
  background: var(--brand-light);
  border: 1px solid var(--brand-soft);
  border-radius: 999px;
  padding: 2px 10px;
  font-family: var(--mono);
}
.stock-head .spacer {
  flex: 1;
}

/* ---------- 图标按钮 ---------- */
.icon-btn {
  display: inline-grid;
  place-items: center;
  width: 30px;
  height: 30px;
  padding: 0;
  border: 1px solid var(--line);
  border-radius: 0.5rem;
  background: transparent;
  color: var(--ink-muted);
  cursor: pointer;
  transition:
    background 0.15s ease,
    border-color 0.15s ease,
    color 0.15s ease;
}
.icon-btn:hover {
  background: var(--surface-muted);
  border-color: var(--brand-soft);
  color: var(--brand);
}
.icon-btn.on {
  background: var(--brand-light);
  border-color: var(--brand-soft);
  color: var(--brand);
}
.icon-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.icon-btn svg {
  width: 16px;
  height: 16px;
}

/* ---------- 同步下拉 ---------- */
.sync-menu {
  position: relative;
}
.sync-pop {
  position: absolute;
  right: 0;
  top: calc(100% + 6px);
  z-index: 20;
  min-width: 158px;
  display: grid;
  gap: 2px;
  padding: 5px;
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: 0.625rem;
  box-shadow: var(--shadow-panel);
}
.sync-item {
  background: transparent;
  border: none;
  color: var(--text);
  text-align: left;
  padding: 7px 10px;
  border-radius: 0.4rem;
  font-size: 0.82rem;
  cursor: pointer;
  white-space: nowrap;
  transition:
    background 0.12s ease,
    color 0.12s ease;
}
.sync-item:hover {
  background: var(--brand-light);
  color: var(--brand);
}
.sync-item:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* ---------- 同步提示条 ---------- */
.sync-banner {
  margin: 0;
  padding: 7px 12px;
  border-radius: 0.6rem;
  font-size: 0.78rem;
  border: 1px solid var(--line);
  background: var(--surface-muted);
}
.sync-banner.ok {
  color: var(--ok);
}
.sync-banner.err {
  color: var(--danger);
}

/* ---------- 页签（分段控件） ---------- */
.stock-tabs {
  display: flex;
  gap: 2px;
  padding: 3px;
  background: var(--surface-muted);
  border: 1px solid var(--line);
  border-radius: 0.7rem;
  overflow-x: auto;
}
.stock-tabs button {
  flex: 1 1 0;
  min-width: max-content;
  background: transparent;
  border: none;
  color: var(--muted);
  border-radius: 0.5rem;
  padding: 7px 14px;
  font-size: 0.82rem;
  cursor: pointer;
  white-space: nowrap;
  transition:
    background 0.15s ease,
    color 0.15s ease,
    box-shadow 0.15s ease;
}
.stock-tabs button:hover {
  color: var(--ink);
}
.stock-tabs button.on {
  background: var(--surface);
  color: var(--brand);
  font-weight: 600;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.08);
}

/* ---------- 内容区 ---------- */
.stock-body {
  min-height: 0;
  overflow: auto;
  display: grid;
  gap: 14px;
  padding-right: 2px;
}

/* ---------- 通用小工具（雷达页） ---------- */
.mono {
  font-family: var(--mono);
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
.q-item {
  display: grid;
  gap: 2px;
  padding: 10px 12px;
  border: 1px solid var(--line);
  border-radius: 0.65rem;
  background: var(--surface);
}
.q-label {
  color: var(--muted);
  font-size: 0.72rem;
}
.q-value {
  font-size: 0.95rem;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
  color: var(--ink);
}

/* ---------- 雷达页 ---------- */
.radar-summary {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(130px, 1fr));
  gap: 8px;
}
.card-titles {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.chip-tag {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  border: 1px solid var(--border);
  border-radius: 999px;
  padding: 3px 10px;
  font-size: 0.78rem;
  background: var(--surface-muted);
  color: var(--ink);
}
</style>

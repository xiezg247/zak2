<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { useStockAnalysis } from '../composables/useStockAnalysis'
import { aiApi } from '../../../api/ai'
import {
  contentApi,
  type TeamReportListItem,
  type TeamReport,
} from '../../../api/content'
import MarkdownView from '../../../components/MarkdownView.vue'
import { fmtDateTime } from '../../../lib/format'

const analysis = useStockAnalysis()

const aiMode = ref<'fast' | 'deep'>('fast')
const aiBusy = ref(false)
const aiStatus = ref('')
const aiReport = ref('')
const aiErr = ref('')
const aiConfigured = ref<boolean | null>(null)
const reportList = ref<TeamReportListItem[]>([])
const reportDetail = ref<TeamReport | null>(null)
const reportListErr = ref('')

async function checkAiStatus() {
  try {
    const st = await aiApi.status()
    aiConfigured.value = st.configured
  } catch {
    aiConfigured.value = false
  }
}

async function loadReportList() {
  if (!analysis.vtSymbol.value) return
  reportListErr.value = ''
  try {
    const page = await contentApi.teamReportsPage(analysis.vtSymbol.value, 1, 20)
    reportList.value = page.items
  } catch (e) {
    reportListErr.value = e instanceof Error ? e.message : '历史研报加载失败'
  }
}

async function openReport(id: number) {
  try {
    reportDetail.value = await contentApi.teamReport(id)
  } catch (e) {
    aiErr.value = e instanceof Error ? e.message : '研报详情加载失败'
  }
}

async function runAi() {
  const vt = analysis.vtSymbol.value
  if (!vt || aiBusy.value || !aiConfigured.value) return
  aiBusy.value = true
  aiErr.value = ''
  aiReport.value = ''
  aiStatus.value = aiMode.value === 'deep' ? '深度预取中…' : '预取中…'
  try {
    await aiApi.streamTeam(
      vt,
      {
        onEvent: (ev) => {
          if (ev.kind === 'started' && ev.agent && ev.agent !== 'system') {
            aiStatus.value = `${ev.label || ev.agent} 分析中…`
          }
          if (ev.kind === 'score' && ev.agent === 'system' && ev.weighted != null) {
            aiStatus.value =
              aiMode.value === 'deep'
                ? `加权 ${ev.weighted} · 三分析师并行中…`
                : `加权 ${ev.weighted} · 首席汇总中…`
          }
          if (ev.kind === 'delta' && ev.agent === 'chief' && ev.content) {
            aiStatus.value = '首席汇总中…'
            aiReport.value += ev.content
          }
          if (ev.kind === 'error') aiErr.value = ev.detail || '团队分析失败'
        },
        onReportSaved: () => {
          aiStatus.value = '研报已保存'
          void loadReportList()
        },
        onDone: () => {
          if (aiStatus.value) aiStatus.value = ''
        },
        onError: (err) => {
          aiErr.value = err
          aiStatus.value = ''
        },
      },
      undefined,
      aiMode.value,
    )
  } catch (e) {
    aiErr.value = e instanceof Error ? e.message : '团队分析失败'
  } finally {
    aiBusy.value = false
  }
}

function maybeLoad() {
  if (analysis.activeTab.value === 'ai' && analysis.vtSymbol.value && !analysis.isLoaded('ai')) {
    analysis.markLoaded('ai')
    void checkAiStatus()
    void loadReportList()
  }
}

onMounted(() => maybeLoad())

watch(() => analysis.activeTab.value, () => maybeLoad())

watch(() => analysis.vtSymbol.value, () => {
  reportList.value = []
  reportDetail.value = null
  aiReport.value = ''
  maybeLoad()
})
</script>

<template>
  <div class="ai-tab">
    <p v-if="aiConfigured === false" class="warn-banner">
      未配置 LLM_API_KEY，团队分析不可用。
    </p>
    <div class="ai-controls">
      <div class="team-mode">
        <label :class="{ on: aiMode === 'fast' }">
          <input v-model="aiMode" type="radio" value="fast" :disabled="aiBusy" />
          <span>快速</span>
        </label>
        <label :class="{ on: aiMode === 'deep' }">
          <input v-model="aiMode" type="radio" value="deep" :disabled="aiBusy" />
          <span>深度</span>
        </label>
      </div>
      <button
        type="button"
        class="primary"
        :disabled="aiBusy || aiConfigured === false"
        @click="runAi"
      >
        {{ aiBusy ? '分析中…' : aiMode === 'deep' ? '深度团队分析' : '团队分析' }}
      </button>
    </div>
    <p v-if="aiStatus" class="hint">{{ aiStatus }}</p>
    <p v-if="aiErr" class="err">{{ aiErr }}</p>
    <div v-if="aiReport" class="report-body">
      <MarkdownView :source="aiReport" />
    </div>

    <section class="report-section">
      <div class="block-head">
        <h4>历史研报</h4>
      </div>
      <p v-if="reportListErr" class="err">{{ reportListErr }}</p>
      <div v-else-if="reportList.length" class="report-list">
        <button
          v-for="r in reportList"
          :key="r.id"
          type="button"
          class="report-item"
          :class="{ on: reportDetail?.id === r.id }"
          @click="openReport(r.id)"
        >
          <span class="report-title">{{ r.title }}</span>
          <span class="muted tiny">{{ r.mode }} · {{ fmtDateTime(r.created_at) }}</span>
        </button>
      </div>
      <p v-else class="hint">暂无历史研报，可点击上方生成。</p>
      <div v-if="reportDetail" class="report-detail">
        <h5>{{ reportDetail.title }}</h5>
        <MarkdownView :source="reportDetail.body" />
      </div>
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
.ai-controls {
  display: flex;
  gap: 10px;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  padding: 10px 12px;
  border: 1px solid var(--line);
  border-radius: 0.65rem;
  background: var(--surface-muted);
}
.team-mode {
  display: inline-flex;
  gap: 8px;
}
.team-mode label {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 0.82rem;
  color: var(--muted);
  cursor: pointer;
}
.team-mode label.on {
  color: var(--brand);
  font-weight: 500;
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
.warn-banner {
  margin: 0;
  padding: 9px 12px;
  border: 1px solid rgba(225, 29, 72, 0.25);
  border-radius: 0.6rem;
  background: rgba(225, 29, 72, 0.06);
  color: var(--danger);
  font-size: 0.82rem;
}
.report-section {
  display: grid;
  gap: 10px;
}
.report-section h4 {
  margin: 0;
  font-size: 0.88rem;
  font-weight: 600;
}
.report-list {
  display: grid;
  gap: 5px;
}
.report-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  background: var(--surface-muted);
  border: 1px solid var(--border);
  border-radius: 0.5rem;
  padding: 7px 11px;
  text-align: left;
  cursor: pointer;
  color: var(--text);
  font-size: 0.82rem;
  transition:
    border-color 0.12s ease,
    background 0.12s ease,
    color 0.12s ease;
}
.report-item:hover,
.report-item.on {
  border-color: var(--brand-soft);
  background: var(--brand-light);
  color: var(--brand);
}
.report-title {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.report-detail {
  border: 1px solid var(--line);
  border-radius: 0.75rem;
  padding: 12px 14px;
  background: var(--surface-muted);
}
.report-detail h5 {
  margin: 0 0 8px;
  font-size: 0.9rem;
}
.report-body :deep(.markdown) {
  font-size: 0.82rem;
  line-height: 1.5;
}
.report-detail :deep(.markdown) {
  font-size: 0.82rem;
  line-height: 1.5;
}
</style>

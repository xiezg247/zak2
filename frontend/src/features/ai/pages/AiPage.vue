<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AppShell from '../../../components/AppShell.vue'
import AiSessionSidebar from '../components/AiSessionSidebar.vue'
import AiChatPanel from '../components/AiChatPanel.vue'
import AiComposer, { type QuickAction } from '../components/AiComposer.vue'
import {
  aiApi,
  type ChatMessage,
  type ConfirmProposal,
  type LlmStatus,
} from '../../../api/ai'
import { useAiSessions } from '../composables/useAiSessions'

const LAST_SYMBOL_KEY = 'zak2.ai.lastSymbol'

const route = useRoute()
const router = useRouter()
const status = ref<LlmStatus | null>(null)
const {
  sessions,
  sessionsPage,
  sessionsPages,
  sessionsTotal,
  sessionId,
  refreshSessions,
  goSessionsPage,
  newSession: createSession,
  removeSession: deleteSession,
  selectSession: setSessionId,
} = useAiSessions()
const messages = ref<ChatMessage[]>([])
const draft = ref('')
const streaming = ref('')
const busy = ref(false)
const error = ref('')
const includeContext = ref(true)
const useTools = ref(true)
const toolStatus = ref('')
const proposals = ref<ConfirmProposal[]>([])
const actingId = ref('')
const teamSymbol = ref('')
const teamMode = ref<'fast' | 'deep'>('fast')
const teamBusy = ref(false)
const teamStatus = ref('')
const teamReport = ref('')
const teamScores = ref<Record<string, { score?: number; summary?: string }>>({})
const teamBodies = ref<Record<string, string>>({})
const teamWeighted = ref<number | null>(null)
const teamSavedReport = ref<{ id: number; title: string; vt: string } | null>(null)
const chatPanelRef = ref<InstanceType<typeof AiChatPanel> | null>(null)
const composerRef = ref<InstanceType<typeof AiComposer> | null>(null)
/** proposal_id -> args 是否展开 */
const argsOpen = ref<Record<string, boolean>>({})

const quickActions: QuickAction[] = [
  {
    id: 'market',
    label: '大势研判',
    icon: '📈',
    mode: 'prompt',
    template:
      '【大势研判】请基于当前市场情绪与主要指数概况，给出今日大势研判：1) 情绪与赚钱效应 2) 主线/风险 3) 操作上偏进攻还是防守。结论要可执行、避免空话。分析仅供研究参考。',
  },
  {
    id: 'trend',
    label: '走势预测',
    icon: '📉',
    mode: 'team',
    needSymbol: true,
    template:
      '【走势预测】标的：/\n请基于投研团队研报，给出短期走势情景推演（偏多/偏空/震荡各自条件），明确关键价位与不确定性，不做荐股承诺。分析仅供研究参考。',
  },
  {
    id: 'trade',
    label: '买卖点研判',
    icon: '⇄',
    mode: 'team',
    needSymbol: true,
    template:
      '【买卖点研判】标的：/\n请基于投研团队研报与我的风控偏好，评估当前位置的买卖参考：支撑/阻力、仓位建议区间、需要等待的条件。分析仅供研究参考。',
  },
  {
    id: 'diagnosis',
    label: '股票诊断',
    icon: '💓',
    mode: 'team',
    needSymbol: true,
    template:
      '【股票诊断】标的：/\n启动投研团队分析（财务/风险/策略），输出完整体检与研报。可用 / 从自选插入代码。',
  },
  {
    id: 'industry',
    label: '行业分析',
    icon: '🏛',
    mode: 'team',
    needSymbol: true,
    template:
      '【行业分析】标的：/\n请基于投研团队研报，延伸分析其所属行业/板块的近期强弱、资金流向与同业对比，并给出产业链位置与关注要点。分析仅供研究参考。',
  },
  {
    id: 'screener',
    label: '选股票',
    icon: '🔍',
    mode: 'prompt',
    template:
      '【选股票】请基于我最近的选股运行结果与雷达/自选概况，解读 Top 命中，说明逻辑与风险，并给出可跟进的标的短名单。分析仅供研究参考。',
  },
  {
    id: 'chart',
    label: '智能图说',
    icon: '📊',
    mode: 'team',
    needSymbol: true,
    template:
      '【智能图说】标的：/\n请基于投研团队研报与近期行情，用文字解读 K 线形态与量价结构：趋势、关键价位、形态含义与注意点。分析仅供研究参考。',
  },
  {
    id: 'review',
    label: 'AI复盘',
    icon: '📋',
    mode: 'prompt',
    template:
      '【AI复盘】请基于我的持仓、自选与近期笔记，做一次复盘：做对了什么、做错了什么、下一步观察清单。分析仅供研究参考。',
  },
]


function toggleArgs(id: string) {
  argsOpen.value = { ...argsOpen.value, [id]: !argsOpen.value[id] }
}

function openNotes(report: { id: number; title: string; vt: string }) {
  router.push({
    path: '/notes',
    query: { symbol: report.vt, report: String(report.id) },
  })
}

const subtitle = computed(() => {
  if (!status.value) return ''
  return status.value.configured ? `${status.value.model} · 已配置` : '未配置 LLM_API_KEY'
})

async function loadMessages() {
  if (!sessionId.value) {
    messages.value = []
    return
  }
  messages.value = await aiApi.messages(sessionId.value)
  await nextTick()
  chatPanelRef.value?.scrollToBottom()
}

async function newSession() {
  await createSession()
  messages.value = []
  proposals.value = []
}

async function removeSession(id: string) {
  const cleared = await deleteSession(id)
  if (cleared) proposals.value = []
  await loadMessages()
}

function pushNote(content: string) {
  if (!sessionId.value) return
  messages.value.push({
    id: Date.now(),
    session_id: sessionId.value,
    role: 'assistant',
    content,
    created_at: new Date().toISOString(),
  })
}

async function onConfirm(p: ConfirmProposal) {
  if (p.status !== 'pending' || actingId.value) return
  actingId.value = p.proposal_id
  try {
    const res = await aiApi.confirmProposal(p.proposal_id)
    p.status = 'confirmed'
    pushNote(`已确认：${res.summary || p.summary}`)
  } catch (e) {
    p.status = 'error'
    p.detail = e instanceof Error ? e.message : '确认失败'
  } finally {
    actingId.value = ''
  }
}

async function onReject(p: ConfirmProposal) {
  if (p.status !== 'pending' || actingId.value) return
  actingId.value = p.proposal_id
  try {
    await aiApi.rejectProposal(p.proposal_id)
    p.status = 'rejected'
    pushNote(`已取消：${p.summary}`)
  } catch (e) {
    p.status = 'error'
    p.detail = e instanceof Error ? e.message : '拒绝失败'
  } finally {
    actingId.value = ''
  }
}

async function send(textOverride?: string) {
  const text = (textOverride ?? draft.value).trim()
  if (!text || busy.value || teamBusy.value) return

  const teamReq = parseTeamQuickSend(text)
  if (teamReq) {
    if (!teamReq.symbol || teamReq.symbol === '/') {
      error.value = '请先填写或用 / 选择股票代码'
      composerRef.value?.focusDraftSlash()
      return
    }
    rememberSymbol(teamReq.symbol)
    draft.value = ''
    composerRef.value?.closeSlash()
    if (!sessionId.value) await newSession()
    messages.value.push({
      id: Date.now(),
      session_id: sessionId.value,
      role: 'user',
      content: text,
      created_at: new Date().toISOString(),
    })
    // 诊断只跑团队；其它 team 快捷：研报落库后再做聚焦追问
    const focusPrompt = teamReq.action.id === 'diagnosis' ? '' : teamReq.focusPrompt
    await runTeam(teamReq.symbol, { focusPrompt })
    return
  }

  const mentioned = extractMentionedSymbol(text)
  if (mentioned) rememberSymbol(mentioned)

  error.value = ''
  if (!sessionId.value) await newSession()
  const sid = sessionId.value
  draft.value = ''
  composerRef.value?.closeSlash()
  messages.value.push({
    id: Date.now(),
    session_id: sid,
    role: 'user',
    content: text,
    created_at: new Date().toISOString(),
  })
  busy.value = true
  streaming.value = ''
  toolStatus.value = ''
  try {
    await aiApi.streamChat(
      sid,
      text,
      {
        onDelta: (t) => {
          toolStatus.value = ''
          streaming.value += t
        },
        onTool: (ev) => {
          if (ev.type === 'tool_started') toolStatus.value = `正在调用 ${ev.name}…`
          else toolStatus.value = `${ev.name} ${ev.ok === false ? '失败' : '完成'}`
        },
        onConfirmRequired: (proposal) => {
          if (!proposals.value.some((x) => x.proposal_id === proposal.proposal_id)) {
            proposals.value.push(proposal)
          }
        },
        onDone: () => {
          streaming.value = ''
          toolStatus.value = ''
          void refreshSessions().then(loadMessages)
        },
        onError: (err) => {
          error.value = err
          streaming.value = ''
          toolStatus.value = ''
        },
      },
      includeContext.value,
      useTools.value,
    )
  } catch (e) {
    error.value = e instanceof Error ? e.message : '发送失败'
  } finally {
    busy.value = false
    toolStatus.value = ''
    if (streaming.value) {
      messages.value.push({
        id: Date.now() + 1,
        session_id: sid,
        role: 'assistant',
        content: streaming.value,
        created_at: new Date().toISOString(),
      })
      streaming.value = ''
    }
  }
}

function loadRememberedSymbol(): string {
  try {
    return localStorage.getItem(LAST_SYMBOL_KEY)?.trim() || ''
  } catch {
    return ''
  }
}

function rememberSymbol(vt: string) {
  const s = vt.trim()
  if (!s || s === '/') return
  teamSymbol.value = s
  try {
    localStorage.setItem(LAST_SYMBOL_KEY, s)
  } catch {
    /* ignore */
  }
}

/** 解析 team 模式快捷草稿：【标签】标的：xxx + 可选聚焦追问 */
function parseTeamQuickSend(
  text: string,
): { action: QuickAction; symbol: string; focusPrompt: string } | null {
  for (const action of quickActions) {
    if (action.mode !== 'team') continue
    const label = action.label.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
    const re = new RegExp(`^【${label}】标的：\\s*([^\\s\\n]*)\\s*\\n?([\\s\\S]*)$`)
    const m = text.match(re)
    if (!m) continue
    return {
      action,
      symbol: (m[1] || '').trim(),
      focusPrompt: (m[2] || '').trim(),
    }
  }
  return null
}

function extractMentionedSymbol(text: string): string {
  const m = text.match(/标的：\s*([A-Za-z0-9.\-]+)/)
  const s = (m?.[1] || '').trim()
  return s && s !== '/' ? s : ''
}

function applyQuickAction(action: QuickAction) {
  if (busy.value || teamBusy.value) return
  error.value = ''
  draft.value = action.template
  composerRef.value?.closeSlash()
  if (action.needSymbol) composerRef.value?.focusDraftSlash()
  else composerRef.value?.focusEnd()
}

async function requestTeam() {
  if (busy.value || teamBusy.value) return
  // 与「股票诊断」同一入口：始终先填入草稿，由用户确认标的后再发送
  const diagnosis = quickActions.find((a) => a.id === 'diagnosis')
  if (!diagnosis) return
  const known = teamSymbol.value.trim()
  if (known) {
    draft.value = diagnosis.template.replace('标的：/', `标的：${known}`)
    error.value = ''
    composerRef.value?.focusEnd()
    return
  }
  applyQuickAction(diagnosis)
}

async function selectSession(id: string) {
  setSessionId(id)
  proposals.value = []
  await loadMessages()
}

async function runTeam(vtOverride?: string, opts?: { focusPrompt?: string }) {
  const vt = (vtOverride ?? teamSymbol.value).trim()
  if (!vt || vt === '/') {
    await requestTeam()
    return
  }
  if (teamBusy.value || busy.value) return
  rememberSymbol(vt)
  composerRef.value?.closeSlash()
  error.value = ''
  teamBusy.value = true
  teamStatus.value = teamMode.value === 'deep' ? '深度预取中…' : '预取中…'
  teamReport.value = ''
  teamScores.value = {}
  teamBodies.value = {}
  teamWeighted.value = null
  teamSavedReport.value = null
  if (!sessionId.value) await newSession()
  let focusAfter = ''
  try {
    await aiApi.streamTeam(
      vt,
      {
        onEvent: (ev) => {
          if (ev.kind === 'started' && ev.agent && ev.agent !== 'system') {
            teamStatus.value = `${ev.label || ev.agent} 分析中…`
          }
          if (ev.kind === 'score' && ev.agent && ev.agent !== 'system') {
            teamScores.value = {
              ...teamScores.value,
              [ev.agent]: { score: ev.score, summary: ev.summary },
            }
          }
          if (ev.kind === 'score' && ev.agent === 'system' && ev.weighted != null) {
            teamWeighted.value = ev.weighted
            teamStatus.value =
              teamMode.value === 'deep'
                ? `加权 ${ev.weighted} · 三分析师并行中…`
                : `加权 ${ev.weighted} · 首席汇总中…`
          }
          if (
            ev.kind === 'delta' &&
            ev.content &&
            ev.agent &&
            (ev.agent === 'financial' || ev.agent === 'risk' || ev.agent === 'strategy')
          ) {
            teamBodies.value = {
              ...teamBodies.value,
              [ev.agent]: (teamBodies.value[ev.agent] || '') + ev.content,
            }
          }
          if (ev.kind === 'delta' && ev.agent === 'chief' && ev.content) {
            teamStatus.value = '首席汇总中…'
            teamReport.value += ev.content
          }
          if (ev.kind === 'error') {
            error.value = ev.detail || '团队分析失败'
          }
        },
        onReportSaved: (ev) => {
          teamSavedReport.value = { id: ev.report_id, title: ev.title, vt: ev.vt_symbol }
          teamStatus.value = '研报已保存'
        },
        onDone: () => {
          if (!teamSavedReport.value) teamStatus.value = ''
          focusAfter = (opts?.focusPrompt || '').trim()
        },
        onError: (err) => {
          error.value = err
          teamStatus.value = ''
        },
      },
      sessionId.value || undefined,
      teamMode.value,
    )
  } catch (e) {
    error.value = e instanceof Error ? e.message : '团队分析失败'
  } finally {
    teamBusy.value = false
    if (!teamStatus.value) teamStatus.value = ''
  }
  await refreshSessions().then(loadMessages)
  // 团队结束后再做聚焦追问（session 里已有研报上下文）
  if (focusAfter && !error.value) {
    await send(focusAfter)
  }
}

onMounted(async () => {
  const fromQuery = String(route.query.symbol || '').trim()
  teamSymbol.value = fromQuery || loadRememberedSymbol()
  try {
    status.value = await aiApi.status()
    await refreshSessions()
    await loadMessages()
  } catch (e) {
    error.value = e instanceof Error ? e.message : '加载失败'
  }
})
</script>

<template>
  <AppShell title="AI 助手" :subtitle="subtitle" active="ai">
    <div class="page">
      <p v-if="status && !status.configured" class="warn-banner">
        未配置 LLM_API_KEY，对话与团队分析不可用。
      </p>
      <p v-if="error" class="err">{{ error }}</p>

      <div class="workspace">
        <AiSessionSidebar
          :sessions="sessions"
          :session-id="sessionId"
          :page="sessionsPage"
          :pages="sessionsPages"
          :total="sessionsTotal"
          v-model:include-context="includeContext"
          v-model:use-tools="useTools"
          @new-session="newSession"
          @select="selectSession"
          @remove="removeSession"
          @page="goSessionsPage"
        />

        <section class="chat">
          <AiChatPanel
            ref="chatPanelRef"
            :messages="messages"
            :streaming="streaming"
            :tool-status="toolStatus"
            :team-status="teamStatus"
            :team-report="teamReport"
            :team-scores="teamScores"
            :team-bodies="teamBodies"
            :team-saved-report="teamSavedReport"
            :proposals="proposals"
            :acting-id="actingId"
            :args-open="argsOpen"
            @confirm="onConfirm"
            @reject="onReject"
            @toggle-args="toggleArgs"
            @open-notes="openNotes"
          />

          <AiComposer
            ref="composerRef"
            v-model:draft="draft"
            v-model:team-mode="teamMode"
            :busy="busy"
            :team-busy="teamBusy"
            :team-weighted="teamWeighted"
            :quick-actions="quickActions"
            @send="send()"
            @apply-quick="applyQuickAction"
            @remember-symbol="rememberSymbol"
          />
        </section>
      </div>
    </div>
  </AppShell>
</template>

<style scoped>
.page {
  height: 100%;
  padding: 16px 20px 20px;
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-height: 0;
}
.err {
  color: var(--danger);
  margin: 0;
  font-size: 0.85rem;
}
.warn-banner {
  margin: 0;
  padding: 8px 12px;
  border: 1px solid var(--brand-soft);
  border-radius: 0.5rem;
  background: var(--brand-light);
  color: var(--brand-dark);
  font-size: 0.82rem;
}

.workspace {
  display: grid;
  grid-template-columns: 236px minmax(0, 1fr);
  grid-template-rows: minmax(0, 1fr);
  gap: 14px;
  flex: 1;
  min-height: 0;
}

/* ---------- 对话区 ---------- */
.chat {
  min-height: 0;
  border: 1px solid var(--line);
  border-radius: 0.9rem;
  background: var(--surface);
  box-shadow: var(--shadow-card);
  position: relative;
  overflow: visible;
  display: grid;
  grid-template-rows: minmax(0, 1fr) auto auto;
  gap: 10px;
  padding: 14px;
}

@media (max-width: 1000px) {
  .workspace {
    grid-template-columns: 220px minmax(0, 1fr);
  }
}
@media (max-width: 760px) {
  .workspace {
    grid-template-columns: 1fr;
    grid-template-rows: none;
  }
  .left {
    overflow: visible;
    max-height: 40vh;
  }
}
</style>

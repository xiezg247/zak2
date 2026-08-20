<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AppShell from '../components/AppShell.vue'
import MarkdownView from '../components/MarkdownView.vue'
import PagerBar from '../components/PagerBar.vue'
import {
  aiApi,
  type ChatMessage,
  type ConfirmProposal,
  type LlmStatus,
  type Session,
} from '../api/ai'
import { watchlistApi, type WatchlistItem } from '../api/watchlist'

const LAST_SYMBOL_KEY = 'zak2.ai.lastSymbol'

const route = useRoute()
const router = useRouter()
const status = ref<LlmStatus | null>(null)
const sessions = ref<Session[]>([])
const sessionsPage = ref(1)
const sessionsPages = ref(0)
const sessionsTotal = ref(0)
const sessionId = ref('')
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
const listEl = ref<HTMLElement | null>(null)
const draftEl = ref<HTMLTextAreaElement | null>(null)
/** proposal_id -> args 是否展开 */
const argsOpen = ref<Record<string, boolean>>({})

type QuickAction = {
  id: string
  label: string
  icon: string
  /** prompt：普通对话；team：发送时走投研团队 */
  mode: 'prompt' | 'team'
  needSymbol?: boolean
  /** 填入输入框的模板；需标的时用 / 作为选票入口 */
  template: string
}

const slashMenuOpen = ref(false)
const slashQuery = ref('')
const slashStart = ref(-1)
const watchlistItems = ref<WatchlistItem[]>([])
const watchlistLoading = ref(false)

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

function sessionTitle(s: { title: string }): string {
  return (s.title || '').trim() || '未命名'
}

function toggleArgs(id: string) {
  argsOpen.value = { ...argsOpen.value, [id]: !argsOpen.value[id] }
}

function hasArgs(p: ConfirmProposal): boolean {
  return Object.keys(p.args || {}).length > 0
}

function formatArgs(p: ConfirmProposal): string {
  try {
    return JSON.stringify(p.args || {}, null, 2)
  } catch {
    return String(p.args)
  }
}

function agentName(key: string): string {
  return key === 'financial' ? '财务' : key === 'risk' ? '风险' : '策略'
}

const subtitle = computed(() => {
  if (!status.value) return ''
  return status.value.configured ? `${status.value.model} · 已配置` : '未配置 LLM_API_KEY'
})

async function refreshSessions() {
  const p = await aiApi.sessionsPage(sessionsPage.value, 20)
  sessions.value = p.items
  sessionsTotal.value = p.total
  sessionsPages.value = p.pages
  if (!sessionId.value && sessions.value.length) {
    sessionId.value = sessions.value[0].id
  }
}

async function goSessionsPage(p: number) {
  sessionsPage.value = p
  await refreshSessions()
}

async function loadMessages() {
  if (!sessionId.value) {
    messages.value = []
    return
  }
  messages.value = await aiApi.messages(sessionId.value)
  await nextTick()
  if (listEl.value) listEl.value.scrollTop = listEl.value.scrollHeight
}

async function newSession() {
  const s = await aiApi.createSession()
  sessions.value = [s, ...sessions.value]
  sessionId.value = s.id
  messages.value = []
  proposals.value = []
}

async function removeSession(id: string) {
  await aiApi.deleteSession(id)
  if (sessionId.value === id) {
    sessionId.value = ''
    proposals.value = []
  }
  await refreshSessions()
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
      focusDraftSlash()
      return
    }
    rememberSymbol(teamReq.symbol)
    draft.value = ''
    slashMenuOpen.value = false
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
  slashMenuOpen.value = false
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

const filteredWatchlist = computed(() => {
  const q = slashQuery.value.trim().toLowerCase()
  const items = watchlistItems.value
  if (!q) return items.slice(0, 40)
  return items
    .filter(
      (i) =>
        i.vt_symbol.toLowerCase().includes(q) ||
        (i.name || '').toLowerCase().includes(q) ||
        i.symbol.toLowerCase().includes(q),
    )
    .slice(0, 40)
})

async function ensureWatchlist() {
  if (watchlistItems.value.length || watchlistLoading.value) return
  watchlistLoading.value = true
  try {
    watchlistItems.value = await watchlistApi.list()
  } catch {
    /* ignore */
  } finally {
    watchlistLoading.value = false
  }
}

function syncSlashMenuFromDraft() {
  const el = draftEl.value
  if (!el) return
  const pos = el.selectionStart ?? draft.value.length
  const before = draft.value.slice(0, pos)
  const m = before.match(/\/([^\s/]*)$/)
  if (!m) {
    slashMenuOpen.value = false
    slashStart.value = -1
    slashQuery.value = ''
    return
  }
  slashStart.value = pos - m[0].length
  slashQuery.value = m[1] || ''
  slashMenuOpen.value = true
  void ensureWatchlist()
}

function onDraftInput() {
  syncSlashMenuFromDraft()
}

function onDraftKeyup() {
  syncSlashMenuFromDraft()
}

function onDraftClick() {
  syncSlashMenuFromDraft()
}

function onDraftBlur() {
  window.setTimeout(() => {
    if (document.activeElement !== draftEl.value) slashMenuOpen.value = false
  }, 120)
}

function insertSlashSymbol(item: WatchlistItem) {
  const start = slashStart.value
  const el = draftEl.value
  if (start < 0 || !el) return
  const pos = el.selectionStart ?? draft.value.length
  const insert = item.vt_symbol
  draft.value = draft.value.slice(0, start) + insert + draft.value.slice(pos)
  rememberSymbol(item.vt_symbol)
  slashMenuOpen.value = false
  slashStart.value = -1
  slashQuery.value = ''
  nextTick(() => {
    const next = start + insert.length
    el.focus()
    el.setSelectionRange(next, next)
  })
}

function focusDraftSlash() {
  nextTick(() => {
    const el = draftEl.value
    if (!el) return
    el.focus()
    const idx = draft.value.indexOf('/')
    if (idx >= 0) {
      el.setSelectionRange(idx, idx + 1)
      syncSlashMenuFromDraft()
    } else {
      const end = draft.value.length
      el.setSelectionRange(end, end)
    }
  })
}

function applyQuickAction(action: QuickAction) {
  if (busy.value || teamBusy.value) return
  error.value = ''
  draft.value = action.template
  slashMenuOpen.value = false
  if (action.needSymbol) focusDraftSlash()
  else {
    nextTick(() => {
      draftEl.value?.focus()
      const end = draft.value.length
      draftEl.value?.setSelectionRange(end, end)
    })
  }
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
    nextTick(() => {
      draftEl.value?.focus()
      const end = draft.value.length
      draftEl.value?.setSelectionRange(end, end)
    })
    return
  }
  applyQuickAction(diagnosis)
}

async function selectSession(id: string) {
  sessionId.value = id
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
  slashMenuOpen.value = false
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
        <aside class="left">
          <section class="side-section">
            <button class="primary block" type="button" @click="newSession">+ 新对话</button>
            <label class="check-label">
              <input v-model="includeContext" type="checkbox" />
              <span>注入自选/选股/回测上下文</span>
            </label>
            <label class="check-label">
              <input v-model="useTools" type="checkbox" />
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
                @click="selectSession(s.id)"
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
                <span class="del" title="删除会话" @click.stop="removeSession(s.id)">×</span>
              </button>
            </div>
            <PagerBar
              :page="sessionsPage"
              :pages="sessionsPages"
              :total="sessionsTotal"
              @change="goSessionsPage"
            />
          </section>
        </aside>

        <section class="chat">
          <div ref="listEl" class="msgs">
            <div
              v-if="
                !messages.length && !streaming && !toolStatus && !proposals.length && !teamReport
              "
              class="welcome"
            >
              <div class="welcome-icon" aria-hidden="true">✦</div>
              <h2>开始对话</h2>
              <p>向 AI 助手提问，或输入股票代码用「投研团队」生成研报。</p>
            </div>

            <template v-for="m in messages" :key="m.id">
              <div class="bubble" :class="m.role">
                <div class="role">{{ m.role === 'user' ? '我' : '助手' }}</div>
                <MarkdownView v-if="m.role === 'assistant'" :source="m.content" />
                <pre v-else>{{ m.content }}</pre>
              </div>
            </template>

            <p v-if="toolStatus" class="status-pill">
              <span class="spinner" aria-hidden="true"></span>{{ toolStatus }}
            </p>
            <p v-if="teamStatus" class="status-pill">
              <span class="spinner" aria-hidden="true"></span>{{ teamStatus }}
            </p>
            <div v-if="Object.keys(teamScores).length" class="team-scores">
              <div v-for="(block, key) in teamScores" :key="key" class="score-card">
                <div class="score-head">
                  <strong>{{ agentName(key) }}</strong>
                  <span class="score-num">{{ block.score ?? '—' }}</span>
                </div>
                <p v-if="block.summary" class="score-summary">{{ block.summary }}</p>
                <div v-if="teamBodies[key]" class="agent-body">
                  <MarkdownView :source="teamBodies[key]" />
                </div>
              </div>
            </div>
            <div v-if="teamReport" class="bubble assistant">
              <div class="role">首席汇总</div>
              <MarkdownView :source="teamReport" />
            </div>

            <p v-if="teamSavedReport" class="saved-tip">
              研报已保存：{{ teamSavedReport.title }}
              <button
                type="button"
                class="link"
                @click="
                  router.push({
                    path: '/notes',
                    query: { symbol: teamSavedReport.vt, report: String(teamSavedReport.id) },
                  })
                "
              >
                在笔记中打开
              </button>
            </p>

            <div v-for="p in proposals" :key="p.proposal_id" class="confirm-card" :class="p.status">
              <div class="confirm-head">
                <strong>待确认写操作</strong>
                <span class="tool-tag">{{ p.tool }}</span>
              </div>
              <div class="confirm-body">{{ p.summary }}</div>
              <button
                v-if="hasArgs(p)"
                type="button"
                class="ghost tiny-btn"
                @click="toggleArgs(p.proposal_id)"
              >
                {{ argsOpen[p.proposal_id] ? '收起参数' : '参数' }}
              </button>
              <pre v-if="hasArgs(p) && argsOpen[p.proposal_id]" class="args-pre">{{
                formatArgs(p)
              }}</pre>
              <p v-if="p.detail" class="err">{{ p.detail }}</p>
              <div v-if="p.status === 'pending'" class="confirm-actions">
                <button
                  type="button"
                  class="primary"
                  :disabled="actingId === p.proposal_id"
                  @click="onConfirm(p)"
                >
                  {{ actingId === p.proposal_id ? '处理中…' : '确认' }}
                </button>
                <button
                  type="button"
                  class="ghost"
                  :disabled="actingId === p.proposal_id"
                  @click="onReject(p)"
                >
                  拒绝
                </button>
              </div>
              <p v-else class="status-line">
                {{
                  p.status === 'confirmed'
                    ? '已确认并写入'
                    : p.status === 'rejected'
                      ? '已拒绝'
                      : '处理失败'
                }}
              </p>
            </div>

            <div v-if="streaming" class="bubble assistant">
              <div class="role">助手</div>
              <MarkdownView :source="streaming" />
            </div>
          </div>

          <div class="quick-bar" role="toolbar" aria-label="投研快捷操作">
            <button
              v-for="action in quickActions"
              :key="action.id"
              type="button"
              class="quick-chip"
              :disabled="busy || teamBusy"
              :title="
                action.needSymbol
                  ? `${action.label}（填入草稿，用 / 选股票）`
                  : `${action.label}（填入草稿）`
              "
              @click="applyQuickAction(action)"
            >
              <span class="quick-icon" aria-hidden="true">{{ action.icon }}</span>
              <span>{{ action.label }}</span>
            </button>
          </div>

          <form class="composer" @submit.prevent="send()">
            <div class="draft-wrap">
              <textarea
                ref="draftEl"
                v-model="draft"
                rows="2"
                placeholder="有问题，尽管问…"
                @input="onDraftInput"
                @keyup="onDraftKeyup"
                @click="onDraftClick"
                @blur="onDraftBlur"
                @keydown.ctrl.enter.prevent="send()"
                @keydown.escape.prevent="slashMenuOpen = false"
              />
              <div v-if="slashMenuOpen" class="slash-menu" @mousedown.prevent>
                <p class="slash-tip">从自选插入股票代码</p>
                <p v-if="watchlistLoading" class="hint muted">加载自选中…</p>
                <p v-else-if="!filteredWatchlist.length" class="hint muted">
                  无匹配，可继续手输代码
                </p>
                <button
                  v-for="item in filteredWatchlist"
                  :key="item.vt_symbol"
                  type="button"
                  class="slash-option"
                  @mousedown.prevent="insertSlashSymbol(item)"
                >
                  <span class="picker-name">{{ item.name || '未命名' }}</span>
                  <span class="picker-code muted">{{ item.vt_symbol }}</span>
                </button>
              </div>
            </div>
            <div class="composer-bar">
              <div class="bar-left">
                <button
                  type="button"
                  class="chip mode-chip"
                  :class="{ deep: teamMode === 'deep' }"
                  :disabled="teamBusy"
                  :title="
                    teamMode === 'deep'
                      ? '深度模式（个股团队类快捷）：三分析师并行，更慢更耗 token'
                      : '快速模式（个股团队类快捷）'
                  "
                  @click="teamMode = teamMode === 'fast' ? 'deep' : 'fast'"
                >
                  <span class="chip-icon" aria-hidden="true">{{
                    teamMode === 'deep' ? '◈' : '⚡'
                  }}</span>
                  <span>{{ teamMode === 'deep' ? '深度' : '快速' }}</span>
                  <span class="chip-caret" aria-hidden="true">▾</span>
                </button>
                <span v-if="teamWeighted != null" class="weighted">加权 {{ teamWeighted }}</span>
                <span class="composer-hint muted">/ 选股 · Ctrl+Enter 发送</span>
              </div>
              <button
                class="send-btn"
                type="submit"
                :disabled="busy || teamBusy || !draft.trim()"
                :title="busy ? '生成中…' : '发送'"
                aria-label="发送"
              >
                <svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true">
                  <path
                    fill="currentColor"
                    d="M3.4 20.4 20.85 12.9a1 1 0 0 0 0-1.8L3.4 3.6a1 1 0 0 0-1.4 1.2l2.2 6.5a1 1 0 0 0 .7.65l8.3 1.05-8.3 1.05a1 1 0 0 0-.7.65l-2.2 6.5a1 1 0 0 0 1.4 1.2Z"
                  />
                </svg>
              </button>
            </div>
          </form>
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

/* ---------- 左栏 ---------- */
.left,
.chat {
  min-height: 0;
  border: 1px solid var(--line);
  border-radius: 0.9rem;
  background: var(--surface);
  box-shadow: var(--shadow-card);
}
.left {
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
.weighted {
  font-size: 0.72rem;
  font-weight: 600;
  color: var(--brand);
  background: var(--brand-light);
  border: 1px solid var(--brand-soft);
  border-radius: 999px;
  padding: 2px 8px;
  line-height: 1.5;
  flex-shrink: 0;
  white-space: nowrap;
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
  transition: background 0.15s ease;
}
.primary:hover:not(:disabled) {
  background: var(--brand-dark);
}
.primary:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}
.primary.block {
  width: 100%;
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

.hint {
  margin: 0;
  font-size: 0.72rem;
}

.sess-list {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: 1px;
  overflow: auto;
  align-content: start;
  scrollbar-width: thin;
  scrollbar-color: var(--line) transparent;
}
.sess-list::-webkit-scrollbar {
  width: 6px;
}
.sess-list::-webkit-scrollbar-thumb {
  background: var(--line);
  border-radius: 999px;
}
.sess {
  position: relative;
  text-align: left;
  background: transparent;
  border: none;
  border-radius: 0.45rem;
  color: var(--ink);
  padding: 5px 6px;
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  flex: 0 0 auto;
  height: auto;
  transition: background 0.15s ease;
}
.sess:hover {
  background: var(--surface-muted);
}
.sess.on {
  background: var(--surface-muted);
}
.sess-icon {
  width: 18px;
  height: 18px;
  border-radius: 999px;
  border: 1px solid var(--line);
  color: var(--ink-faint);
  display: inline-grid;
  place-items: center;
  flex-shrink: 0;
  background: var(--surface);
}
.sess-icon svg {
  width: 11px;
  height: 11px;
}
.sess.on .sess-icon {
  border-color: var(--brand-soft);
  color: var(--brand);
  background: var(--brand-light);
}
.sess-title {
  font-size: 0.8125rem;
  font-weight: 400;
  color: var(--ink);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
  min-width: 0;
  padding-right: 14px;
  line-height: 1.3;
}
.del {
  position: absolute;
  right: 4px;
  top: 50%;
  transform: translateY(-50%);
  color: var(--ink-faint);
  font-size: 0.9rem;
  line-height: 1;
  padding: 1px 4px;
  border-radius: 0.3rem;
  opacity: 0;
  transition: opacity 0.12s ease;
}
.sess:hover .del {
  opacity: 1;
}
.del:hover {
  color: var(--danger);
  background: rgba(225, 29, 72, 0.08);
}

/* ---------- 对话区 ---------- */
.chat {
  position: relative;
  overflow: visible;
  display: grid;
  grid-template-rows: minmax(0, 1fr) auto auto;
  gap: 10px;
  padding: 14px;
}
.msgs {
  overflow: auto;
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding-right: 4px;
  scrollbar-width: thin;
  scrollbar-color: var(--line) transparent;
}
.msgs::-webkit-scrollbar {
  width: 8px;
}
.msgs::-webkit-scrollbar-thumb {
  background: var(--line);
  border-radius: 999px;
}

.welcome {
  margin: auto;
  text-align: center;
  display: grid;
  gap: 8px;
  justify-items: center;
  color: var(--ink-muted);
  padding: 32px;
}
.welcome-icon {
  width: 52px;
  height: 52px;
  border-radius: 16px;
  display: grid;
  place-items: center;
  font-size: 1.5rem;
  color: var(--brand);
  background: var(--brand-light);
  border: 1px solid var(--brand-soft);
}
.welcome h2 {
  margin: 4px 0 0;
  font-size: 1.1rem;
  color: var(--ink);
}
.welcome p {
  margin: 0;
  font-size: 0.85rem;
}

.bubble {
  max-width: 78%;
  border-radius: 0.8rem;
  padding: 10px 14px;
  display: grid;
  gap: 4px;
}
.bubble.user {
  align-self: flex-end;
  background: var(--brand);
  color: var(--brand-foreground);
  border-bottom-right-radius: 0.25rem;
}
.bubble.assistant {
  align-self: flex-start;
  background: var(--surface-muted);
  border: 1px solid var(--line-soft);
  border-bottom-left-radius: 0.25rem;
}
.role {
  font-size: 0.72rem;
  opacity: 0.7;
  font-weight: 600;
}
pre {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
  font-family: var(--font);
  font-size: 0.88rem;
  line-height: 1.6;
}

.status-pill {
  align-self: flex-start;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  margin: 0;
  padding: 5px 10px;
  border-radius: 999px;
  background: var(--brand-light);
  color: var(--brand-dark);
  font-size: 0.78rem;
}
.spinner {
  width: 12px;
  height: 12px;
  border: 2px solid var(--brand-soft);
  border-top-color: var(--brand);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.team-scores {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
}
.score-card {
  border: 1px solid var(--line-soft);
  border-radius: 0.6rem;
  padding: 10px 12px;
  background: var(--surface);
  display: grid;
  gap: 6px;
}
.score-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  font-size: 0.82rem;
}
.score-num {
  font-size: 1.25rem;
  font-weight: 700;
  color: var(--brand);
}
.score-summary {
  margin: 0;
  font-size: 0.78rem;
  color: var(--ink-muted);
}
.agent-body {
  margin: 4px 0 0;
  max-height: 140px;
  overflow: auto;
  background: var(--surface-muted);
  border-radius: 0.4rem;
  padding: 8px 10px;
}
.agent-body :deep(.markdown) {
  font-size: 0.76rem;
  line-height: 1.5;
  color: var(--ink);
}

.saved-tip {
  margin: 0;
  font-size: 0.82rem;
  color: var(--ok);
  display: flex;
  gap: 10px;
  align-items: center;
  flex-wrap: wrap;
  padding: 8px 10px;
  background: rgba(22, 163, 74, 0.08);
  border: 1px solid rgba(22, 163, 74, 0.28);
  border-radius: 0.5rem;
}
.saved-tip .link {
  background: none;
  border: none;
  color: var(--brand);
  text-decoration: underline;
  text-underline-offset: 2px;
  padding: 0;
  cursor: pointer;
}

.confirm-card {
  border: 1px solid var(--brand);
  border-radius: 0.75rem;
  padding: 12px 14px;
  background: var(--brand-light);
  display: grid;
  gap: 8px;
}
.confirm-card.confirmed {
  border-color: var(--line);
  background: var(--surface-muted);
}
.confirm-card.rejected,
.confirm-card.error {
  border-color: var(--line);
  background: var(--surface-muted);
}
.confirm-head {
  display: flex;
  gap: 10px;
  align-items: center;
  justify-content: space-between;
}
.tool-tag {
  font-size: 0.72rem;
  color: var(--brand-dark);
  background: var(--surface);
  border: 1px solid var(--brand-soft);
  border-radius: 999px;
  padding: 1px 8px;
}
.confirm-body {
  font-size: 0.88rem;
  line-height: 1.5;
  color: var(--ink);
}
.confirm-actions {
  display: flex;
  gap: 8px;
}
.status-line {
  margin: 0;
  font-size: 0.78rem;
  color: var(--ink-muted);
}
.args-pre {
  margin: 0;
  padding: 8px 10px;
  font-size: 0.74rem;
  overflow: auto;
  max-height: 160px;
  background: var(--surface);
  border-radius: 0.4rem;
  border: 1px solid var(--line-soft);
}
.tiny-btn {
  justify-self: start;
  font-size: 0.78rem;
  padding: 4px 10px;
}

.quick-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  overflow-x: auto;
  padding: 0 2px 2px;
  scrollbar-width: none;
  mask-image: linear-gradient(90deg, #000 85%, transparent);
}
.quick-bar::-webkit-scrollbar {
  display: none;
}
.quick-chip {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  flex-shrink: 0;
  border: 1px solid var(--line);
  background: var(--surface);
  color: var(--ink-muted);
  border-radius: 0.7rem;
  padding: 7px 12px;
  font-size: 0.8rem;
  white-space: nowrap;
  transition:
    background 0.15s ease,
    border-color 0.15s ease,
    color 0.15s ease,
    transform 0.12s ease;
}
.quick-chip:hover:not(:disabled) {
  background: var(--brand-light);
  border-color: var(--brand-soft);
  color: var(--brand-dark);
  transform: translateY(-1px);
}
.quick-chip:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.quick-icon {
  font-size: 0.85rem;
  line-height: 1;
}

.draft-wrap {
  position: relative;
}
.slash-menu {
  position: absolute;
  left: 0;
  right: 0;
  bottom: calc(100% + 8px);
  max-height: 220px;
  overflow: auto;
  z-index: 30;
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 8px;
  border-radius: 0.85rem;
  border: 1px solid var(--line);
  background: var(--surface);
  box-shadow: 0 8px 28px rgba(0, 0, 0, 0.1);
  scrollbar-width: thin;
}
.slash-tip {
  margin: 0 0 4px;
  padding: 5px 8px;
  font-size: 0.72rem;
  color: var(--brand-dark);
  background: var(--brand-light);
  border-radius: 0.45rem;
}
.slash-option {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  text-align: left;
  border: none;
  background: transparent;
  border-radius: 0.5rem;
  padding: 8px 10px;
  color: var(--ink);
}
.slash-option:hover {
  background: var(--brand-light);
}
.picker-name {
  font-size: 0.82rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  min-width: 0;
}
.picker-code {
  font-size: 0.72rem;
  flex-shrink: 0;
}

.composer {
  position: relative;
  overflow: visible;
  display: grid;
  gap: 0;
  padding: 16px 16px 12px;
  border: 1px solid var(--line);
  border-radius: 1.5rem;
  background: var(--surface);
  box-shadow:
    0 1px 2px rgba(0, 0, 0, 0.03),
    0 8px 28px rgba(0, 0, 0, 0.05);
  transition:
    border-color 0.18s ease,
    box-shadow 0.18s ease;
}
.composer:focus-within {
  border-color: var(--brand-soft);
  box-shadow:
    0 0 0 3px rgba(230, 100, 50, 0.1),
    0 8px 28px rgba(0, 0, 0, 0.06);
}
.composer textarea {
  width: 100%;
  background: transparent;
  border: none;
  color: var(--ink);
  padding: 2px 2px 12px;
  resize: none;
  font-size: 0.95rem;
  line-height: 1.6;
  box-shadow: none;
  min-height: 56px;
  max-height: 180px;
}
.composer textarea:focus {
  border: none;
  box-shadow: none;
  outline: none;
}
.composer textarea::placeholder {
  color: var(--ink-faint);
}
.composer-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  min-width: 0;
  padding-top: 10px;
  border-top: 1px solid var(--line-soft);
}
.bar-left {
  display: flex;
  align-items: center;
  gap: 6px;
  flex: 1;
  min-width: 0;
  overflow-x: auto;
  scrollbar-width: none;
}
.bar-left::-webkit-scrollbar {
  display: none;
}
.bar-sep {
  width: 1px;
  height: 14px;
  background: var(--line);
  flex-shrink: 0;
  margin: 0 2px;
}
.composer-hint {
  margin-left: 4px;
  font-size: 0.7rem;
  white-space: nowrap;
  opacity: 0.75;
}
.chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  border: 1px solid var(--line);
  background: var(--surface);
  color: var(--ink-muted);
  border-radius: 999px;
  padding: 5px 11px;
  font-size: 0.78rem;
  white-space: nowrap;
  flex-shrink: 0;
  transition:
    background 0.15s ease,
    color 0.15s ease,
    border-color 0.15s ease;
}
.chip:hover:not(:disabled) {
  background: var(--surface-muted);
  color: var(--ink);
  border-color: var(--line);
}
.chip:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.mode-chip {
  color: var(--brand);
  background: var(--brand-light);
  border-color: var(--brand-soft);
  font-weight: 500;
}
.mode-chip:hover:not(:disabled) {
  background: #fde6da;
  color: var(--brand-dark);
  border-color: var(--brand-soft);
}
.mode-chip.deep {
  color: var(--brand-dark);
}
.chip-icon {
  font-size: 0.85rem;
  line-height: 1;
}
.chip-caret {
  font-size: 0.65rem;
  opacity: 0.7;
  margin-left: 1px;
}
.composer .send-btn {
  width: 36px;
  height: 36px;
  padding: 0;
  border: none;
  border-radius: 999px;
  background: var(--brand);
  color: var(--brand-foreground);
  display: inline-grid;
  place-items: center;
  flex-shrink: 0;
  box-shadow: 0 2px 8px rgba(230, 100, 50, 0.28);
  transition:
    background 0.15s ease,
    opacity 0.15s ease,
    transform 0.12s ease,
    box-shadow 0.15s ease;
}
.composer .send-btn:hover:not(:disabled) {
  background: var(--brand-dark);
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(230, 100, 50, 0.35);
}
.composer .send-btn:disabled {
  opacity: 0.35;
  cursor: not-allowed;
  box-shadow: none;
  transform: none;
}

.muted {
  color: var(--ink-muted);
  font-size: 0.75rem;
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
  .team-scores {
    grid-template-columns: 1fr;
  }
}
@media (max-width: 600px) {
  .composer-hint {
    display: none;
  }
}
</style>

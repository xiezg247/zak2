<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AppShell from '../components/AppShell.vue'
import PagerBar from '../components/PagerBar.vue'
import {
  aiApi,
  type ChatMessage,
  type ConfirmProposal,
  type LlmStatus,
  type Session,
} from '../api/ai'

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
const teamSymbol = ref('600519.SSE')
const teamMode = ref<'fast' | 'deep'>('fast')
const teamBusy = ref(false)
const teamStatus = ref('')
const teamReport = ref('')
const teamScores = ref<Record<string, { score?: number; summary?: string }>>({})
const teamBodies = ref<Record<string, string>>({})
const teamWeighted = ref<number | null>(null)
const teamSavedReport = ref<{ id: number; title: string; vt: string } | null>(null)
const listEl = ref<HTMLElement | null>(null)
const sessionFilter = ref('')
/** proposal_id -> args 是否展开 */
const argsOpen = ref<Record<string, boolean>>({})

function sessionTitle(s: { title: string }): string {
  return (s.title || '').trim() || '未命名'
}

const displayedSessions = computed(() => {
  const q = sessionFilter.value.trim().toLowerCase()
  if (!q) return sessions.value
  return sessions.value.filter((s) => sessionTitle(s).toLowerCase().includes(q))
})

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

async function send() {
  const text = draft.value.trim()
  if (!text || busy.value) return
  error.value = ''
  if (!sessionId.value) await newSession()
  const sid = sessionId.value
  draft.value = ''
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

async function selectSession(id: string) {
  sessionId.value = id
  proposals.value = []
  await loadMessages()
}

async function runTeam() {
  const vt = teamSymbol.value.trim()
  if (!vt || teamBusy.value || busy.value) return
  error.value = ''
  teamBusy.value = true
  teamStatus.value = teamMode.value === 'deep' ? '深度预取中…' : '预取中…'
  teamReport.value = ''
  teamScores.value = {}
  teamBodies.value = {}
  teamWeighted.value = null
  teamSavedReport.value = null
  if (!sessionId.value) await newSession()
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
          void refreshSessions().then(loadMessages)
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
}

onMounted(async () => {
  const s = String(route.query.symbol || '').trim()
  if (s) teamSymbol.value = s
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
      <p v-if="status && !status.configured" class="warn-banner muted">
        未配置 LLM_API_KEY，对话与团队分析不可用。
      </p>
      <p v-if="error" class="err">{{ error }}</p>
      <div class="workspace">
        <aside class="left">
          <button class="primary" type="button" @click="newSession">新对话</button>
          <label class="ctx">
            <input v-model="includeContext" type="checkbox" />
            注入自选/选股/回测上下文
          </label>
          <label class="ctx">
            <input v-model="useTools" type="checkbox" />
            启用工具（Agent）
          </label>
          <div class="team-box">
            <div class="team-title">投研团队</div>
            <input v-model="teamSymbol" placeholder="600519.SSE" @keyup.enter="runTeam" />
            <div class="team-mode">
              <label>
                <input v-model="teamMode" type="radio" value="fast" :disabled="teamBusy" />
                快速
              </label>
              <label>
                <input v-model="teamMode" type="radio" value="deep" :disabled="teamBusy" />
                深度
              </label>
            </div>
            <button
              type="button"
              class="primary"
              :disabled="teamBusy || busy || !teamSymbol.trim()"
              @click="runTeam"
            >
              {{ teamBusy ? '分析中…' : teamMode === 'deep' ? '深度团队分析' : '团队分析' }}
            </button>
            <p v-if="teamMode === 'deep'" class="muted tiny">三分析师并行 LLM，更慢更耗 token</p>
            <p v-if="teamWeighted != null" class="muted">加权分 {{ teamWeighted }}</p>
          </div>
          <div v-if="sessions.length" class="session-filter">
            <input v-model="sessionFilter" placeholder="过滤会话" />
          </div>
          <p v-if="!sessions.length" class="muted tiny sess-empty">暂无会话，点上方新对话</p>
          <p v-else-if="!displayedSessions.length" class="muted tiny sess-empty">无匹配会话</p>
          <button
            v-for="s in displayedSessions"
            :key="s.id"
            type="button"
            class="sess"
            :class="{ on: sessionId === s.id }"
            @click="selectSession(s.id)"
          >
            <span>{{ sessionTitle(s) }}</span>
            <span class="muted">{{ s.updated_at }}</span>
            <span class="del" @click.stop="removeSession(s.id)">删</span>
          </button>
          <PagerBar
            :page="sessionsPage"
            :pages="sessionsPages"
            :total="sessionsTotal"
            @change="goSessionsPage"
          />
        </aside>

        <section class="right">
          <div class="msgs" ref="listEl">
            <div v-for="m in messages" :key="m.id" class="bubble" :class="m.role">
              <div class="role">{{ m.role === 'user' ? '我' : '助手' }}</div>
              <pre>{{ m.content }}</pre>
            </div>
            <p v-if="toolStatus" class="tool-status">{{ toolStatus }}</p>
            <p v-if="teamStatus" class="tool-status">{{ teamStatus }}</p>
            <div v-if="Object.keys(teamScores).length" class="team-scores">
              <div v-for="(block, key) in teamScores" :key="key" class="score-card">
                <strong>{{
                  key === 'financial' ? '财务' : key === 'risk' ? '风险' : '策略'
                }}</strong>
                <span>{{ block.score ?? '—' }}</span>
                <p class="muted">{{ block.summary || '' }}</p>
                <pre v-if="teamBodies[key]" class="agent-body">{{ teamBodies[key] }}</pre>
              </div>
            </div>
            <div v-if="teamReport" class="bubble assistant">
              <div class="role">首席汇总</div>
              <pre>{{ teamReport }}</pre>
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
                <span class="muted">{{ p.tool }}</span>
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
              <div class="confirm-actions" v-if="p.status === 'pending'">
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
              <p v-else class="muted status-line">
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
              <pre>{{ streaming }}</pre>
            </div>
            <p
              v-if="
                !messages.length && !streaming && !toolStatus && !proposals.length && !teamReport
              "
              class="empty muted"
            >
              开始提问，或左侧输入代码点「团队分析」
            </p>
          </div>
          <form class="composer" @submit.prevent="send">
            <textarea
              v-model="draft"
              rows="3"
              placeholder="输入问题，Enter+Ctrl 发送"
              @keydown.ctrl.enter.prevent="send"
            />
            <button class="primary" type="submit" :disabled="busy || teamBusy || !draft.trim()">
              {{ busy ? '生成中…' : '发送' }}
            </button>
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
  min-height: 0;
}
.err {
  color: var(--danger);
  margin: 0 0 8px;
}
.warn-banner {
  margin: 0 0 8px;
  padding: 8px 10px;
  border: 1px solid var(--border);
  border-radius: 0.5rem;
  background: var(--surface-muted, var(--bg-elevated));
}
.session-filter input {
  width: 100%;
  box-sizing: border-box;
  background: var(--bg);
  border: 1px solid var(--border);
  color: var(--text);
  border-radius: 0.5rem;
  padding: 6px 10px;
  font-size: 0.85rem;
}
.sess-empty {
  margin: 4px 0;
}
.args-pre {
  margin: 6px 0 0;
  padding: 8px;
  font-size: 0.75rem;
  overflow: auto;
  max-height: 160px;
  background: var(--bg);
  border-radius: 0.4rem;
  border: 1px solid var(--border);
}
.tiny-btn {
  justify-self: start;
  margin-top: 6px;
  font-size: 0.8rem;
  padding: 4px 8px;
}
.workspace {
  display: grid;
  grid-template-columns: 280px 1fr;
  gap: 14px;
  flex: 1;
  min-height: 0;
}
.left,
.right {
  border: 1px solid var(--line);
  border-radius: 0.75rem;
  background: var(--surface);
  box-shadow: var(--shadow-card);
  display: grid;
  gap: 10px;
  padding: 14px;
  min-height: 0;
}
.left {
  align-content: start;
  overflow: auto;
}
.right {
  grid-template-rows: 1fr auto;
}
.ctx {
  display: flex;
  gap: 6px;
  align-items: center;
  color: var(--muted);
  font-size: 0.8rem;
}
.team-box {
  display: grid;
  gap: 8px;
  padding: 10px;
  border: 1px solid var(--border);
  border-radius: 0.75rem;
  background: var(--bg);
}
.team-title {
  font-size: 0.85rem;
  font-weight: 600;
}
.team-mode {
  display: flex;
  gap: 12px;
  font-size: 0.8rem;
  color: var(--muted);
}
.team-mode label {
  display: flex;
  gap: 4px;
  align-items: center;
  cursor: pointer;
}
.tiny {
  font-size: 0.72rem;
  margin: 0;
}
.team-box input {
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: 0.5rem;
  color: var(--text);
  padding: 8px 10px;
}
.team-scores {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
}
.score-card {
  border: 1px solid var(--border);
  border-radius: 0.5rem;
  padding: 8px 10px;
  background: var(--bg);
  display: grid;
  gap: 4px;
  font-size: 0.85rem;
}
.score-card span {
  font-size: 1.2rem;
  font-weight: 700;
}
.agent-body {
  margin: 6px 0 0;
  white-space: pre-wrap;
  font-size: 0.78rem;
  line-height: 1.4;
  color: var(--text);
  max-height: 160px;
  overflow: auto;
}
.sess {
  text-align: left;
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 0.5rem;
  color: var(--text);
  padding: 8px;
  display: grid;
  gap: 2px;
  position: relative;
}
.sess.on {
  border-color: var(--accent);
}
.del {
  position: absolute;
  right: 8px;
  top: 8px;
  color: var(--muted);
  font-size: 0.75rem;
}
.msgs {
  overflow: auto;
  display: grid;
  gap: 10px;
  align-content: start;
  padding-right: 4px;
}
.bubble {
  border: 1px solid var(--border);
  border-radius: 0.75rem;
  padding: 10px 12px;
  background: var(--bg);
}
.bubble.user {
  border-color: var(--brand-soft);
}
.bubble.assistant {
  border-color: var(--line);
}
.tool-status {
  margin: 0;
  color: var(--muted);
  font-size: 0.8rem;
  padding: 4px 8px;
}
.saved-tip {
  margin: 0;
  font-size: 0.85rem;
  color: var(--accent);
  display: flex;
  gap: 10px;
  align-items: center;
  flex-wrap: wrap;
  padding: 4px 8px;
}
.saved-tip .link {
  background: none;
  border: none;
  color: var(--accent);
  text-decoration: underline;
  padding: 0;
  cursor: pointer;
}
.confirm-card {
  border: 1px solid var(--accent);
  border-radius: 0.75rem;
  padding: 10px 12px;
  background: var(--surface-muted);
  display: grid;
  gap: 8px;
}
.confirm-card.confirmed {
  border-color: var(--line);
  opacity: 0.85;
}
.confirm-card.rejected,
.confirm-card.error {
  border-color: var(--border);
  opacity: 0.75;
}
.confirm-head {
  display: flex;
  gap: 10px;
  align-items: baseline;
  justify-content: space-between;
}
.confirm-body {
  font-size: 0.9rem;
  line-height: 1.4;
}
.confirm-actions {
  display: flex;
  gap: 8px;
}
.ghost {
  background: transparent;
  border: 1px solid var(--border);
  color: var(--text);
  border-radius: 0.5rem;
  padding: 8px 12px;
}
.status-line {
  margin: 0;
}
.role {
  color: var(--muted);
  font-size: 0.75rem;
  margin-bottom: 4px;
}
pre {
  margin: 0;
  white-space: pre-wrap;
  font-family: var(--font);
  font-size: 0.9rem;
  line-height: 1.5;
}
.composer {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 8px;
  align-items: end;
}
textarea {
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 0.5rem;
  color: var(--text);
  padding: 10px;
  resize: vertical;
}
.primary {
  background: var(--accent);
  border: none;
  color: var(--brand-foreground);
  border-radius: 0.5rem;
  padding: 10px 14px;
  font-weight: 600;
}
.primary:disabled {
  opacity: 0.6;
}
.muted {
  color: var(--muted);
  font-size: 0.75rem;
}
.empty {
  text-align: center;
  padding: 40px;
}
@media (max-width: 900px) {
  .workspace {
    grid-template-columns: 1fr;
  }
}
</style>

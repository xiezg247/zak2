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
      <p v-if="status && !status.configured" class="warn-banner">未配置 LLM_API_KEY，对话与团队分析不可用。</p>
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

          <section class="side-section team">
            <div class="side-title-row">
              <h2 class="side-title">投研团队</h2>
              <span v-if="teamWeighted != null" class="weighted">{{ teamWeighted }}</span>
            </div>
            <input
              v-model="teamSymbol"
              class="filter"
              placeholder="600519.SSE"
              @keyup.enter="runTeam"
            />
            <div class="team-mode">
              <label :class="{ on: teamMode === 'fast' }">
                <input v-model="teamMode" type="radio" value="fast" :disabled="teamBusy" />
                <span>快速</span>
              </label>
              <label :class="{ on: teamMode === 'deep' }">
                <input v-model="teamMode" type="radio" value="deep" :disabled="teamBusy" />
                <span>深度</span>
              </label>
            </div>
            <button
              type="button"
              class="primary block"
              :disabled="teamBusy || busy || !teamSymbol.trim()"
              @click="runTeam"
            >
              {{ teamBusy ? '分析中…' : teamMode === 'deep' ? '深度团队分析' : '团队分析' }}
            </button>
            <p v-if="teamMode === 'deep'" class="hint muted">三分析师并行 LLM，更慢更耗 token</p>
          </section>

          <section class="side-section grow">
            <div class="side-title-row">
              <h2 class="side-title">会话</h2>
              <span class="count muted">{{ sessionsTotal }}</span>
            </div>
            <input v-model="sessionFilter" class="filter" placeholder="过滤会话" />
            <p v-if="!sessions.length" class="hint muted">暂无会话，点上方新对话</p>
            <p v-else-if="!displayedSessions.length" class="hint muted">无匹配会话</p>
            <div class="sess-list">
              <button
                v-for="s in displayedSessions"
                :key="s.id"
                type="button"
                class="sess"
                :class="{ on: sessionId === s.id }"
                @click="selectSession(s.id)"
              >
                <span class="sess-title">{{ sessionTitle(s) }}</span>
                <span class="sess-time muted">{{ s.updated_at }}</span>
                <span class="del" title="删除会话" @click.stop="removeSession(s.id)">删</span>
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

        <section class="right">
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

          <form class="composer" @submit.prevent="send">
            <textarea
              v-model="draft"
              rows="3"
              placeholder="输入问题，Ctrl+Enter 发送"
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
  grid-template-columns: 280px minmax(0, 1fr);
  gap: 14px;
  flex: 1;
  min-height: 0;
}

/* ---------- 左栏 ---------- */
.left,
.right {
  min-height: 0;
  border: 1px solid var(--line);
  border-radius: 0.9rem;
  background: var(--surface);
  box-shadow: var(--shadow-card);
}
.left {
  display: flex;
  flex-direction: column;
  padding: 14px;
  overflow: auto;
}
.side-section {
  display: grid;
  gap: 8px;
  padding-bottom: 16px;
  border-bottom: 1px solid var(--line-soft);
}
.side-section + .side-section {
  padding-top: 16px;
}
.side-section.grow {
  flex: 1;
  border-bottom: none;
  padding-bottom: 0;
}
.side-title {
  margin: 0;
  font-size: 0.72rem;
  font-weight: 600;
  letter-spacing: 0.08em;
  color: var(--ink-faint);
}
.side-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.count {
  font-size: 0.75rem;
}
.weighted {
  font-size: 0.8rem;
  font-weight: 700;
  color: var(--brand);
  background: var(--brand-light);
  border: 1px solid var(--brand-soft);
  border-radius: 999px;
  padding: 0 10px;
  line-height: 1.6;
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

.filter {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: 0.5rem;
  color: var(--ink);
  padding: 8px 10px;
  width: 100%;
}
.team-mode {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 6px;
}
.team-mode label {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 5px;
  border: 1px solid var(--line);
  border-radius: 0.5rem;
  padding: 6px 0;
  font-size: 0.8rem;
  color: var(--ink-muted);
  cursor: pointer;
  transition:
    border-color 0.15s ease,
    background 0.15s ease,
    color 0.15s ease;
}
.team-mode label.on {
  border-color: var(--brand-soft);
  background: var(--brand-light);
  color: var(--brand);
}
.team-mode input {
  accent-color: var(--brand);
}
.hint {
  margin: 0;
  font-size: 0.72rem;
}

.sess-list {
  display: grid;
  gap: 3px;
  overflow: auto;
}
.sess {
  position: relative;
  text-align: left;
  background: transparent;
  border: 1px solid transparent;
  border-radius: 0.6rem;
  color: var(--ink);
  padding: 8px 10px;
  display: grid;
  gap: 2px;
  transition:
    background 0.15s ease,
    border-color 0.15s ease;
}
.sess:hover {
  background: var(--surface-muted);
}
.sess.on {
  background: var(--brand-light);
  border-color: var(--brand-soft);
}
.sess-title {
  font-size: 0.85rem;
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  padding-right: 24px;
}
.sess-time {
  font-size: 0.7rem;
}
.del {
  position: absolute;
  right: 8px;
  top: 50%;
  transform: translateY(-50%);
  color: var(--ink-faint);
  font-size: 0.72rem;
  padding: 2px 4px;
  border-radius: 0.3rem;
}
.del:hover {
  color: var(--danger);
  background: #fff1f2;
}

/* ---------- 右栏 ---------- */
.right {
  display: grid;
  grid-template-rows: minmax(0, 1fr) auto;
  gap: 10px;
  padding: 14px;
}
.msgs {
  overflow: auto;
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding-right: 4px;
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
  padding: 6px 10px;
  background: #ecfdf5;
  border: 1px solid #86efac;
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

.composer {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 8px;
  align-items: end;
}
.composer textarea {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: 0.7rem;
  color: var(--ink);
  padding: 10px 12px;
  resize: none;
  font-size: 0.88rem;
  line-height: 1.5;
}
.composer textarea:focus {
  border-color: var(--brand);
  box-shadow: 0 0 0 3px rgba(230, 100, 50, 0.15);
  outline: none;
}
.composer .primary {
  padding: 12px 20px;
}

.muted {
  color: var(--ink-muted);
  font-size: 0.75rem;
}

@media (max-width: 900px) {
  .workspace {
    grid-template-columns: 1fr;
  }
  .left,
  .right {
    overflow: visible;
  }
  .team-scores {
    grid-template-columns: 1fr;
  }
}
</style>

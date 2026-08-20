<script setup lang="ts">
import { ref } from 'vue'
import MarkdownView from '../../../components/MarkdownView.vue'
import type { ChatMessage, ConfirmProposal } from '../../../api/ai'

defineProps<{
  messages: ChatMessage[]
  streaming: string
  toolStatus: string
  teamStatus: string
  teamReport: string
  teamScores: Record<string, { score?: number; summary?: string }>
  teamBodies: Record<string, string>
  teamSavedReport: { id: number; title: string; vt: string } | null
  proposals: ConfirmProposal[]
  actingId: string
  argsOpen: Record<string, boolean>
}>()

const emit = defineEmits<{
  confirm: [p: ConfirmProposal]
  reject: [p: ConfirmProposal]
  toggleArgs: [id: string]
  openNotes: [report: { id: number; title: string; vt: string }]
}>()

const listEl = ref<HTMLElement | null>(null)

function agentName(key: string): string {
  return key === 'financial' ? '财务' : key === 'risk' ? '风险' : '策略'
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

function scrollToBottom() {
  if (listEl.value) listEl.value.scrollTop = listEl.value.scrollHeight
}

defineExpose({ el: listEl, scrollToBottom })
</script>

<template>
  <div ref="listEl" class="msgs">
    <div
      v-if="!messages.length && !streaming && !toolStatus && !proposals.length && !teamReport"
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
      <button type="button" class="link" @click="emit('openNotes', teamSavedReport)">
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
        @click="emit('toggleArgs', p.proposal_id)"
      >
        {{ argsOpen[p.proposal_id] ? '收起参数' : '参数' }}
      </button>
      <pre v-if="hasArgs(p) && argsOpen[p.proposal_id]" class="args-pre">{{ formatArgs(p) }}</pre>
      <p v-if="p.detail" class="err">{{ p.detail }}</p>
      <div v-if="p.status === 'pending'" class="confirm-actions">
        <button
          type="button"
          class="primary"
          :disabled="actingId === p.proposal_id"
          @click="emit('confirm', p)"
        >
          {{ actingId === p.proposal_id ? '处理中…' : '确认' }}
        </button>
        <button
          type="button"
          class="ghost"
          :disabled="actingId === p.proposal_id"
          @click="emit('reject', p)"
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
</template>

<style scoped>
.msgs {
  overflow: auto;
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding-right: 4px;
  scrollbar-width: thin;
  scrollbar-color: var(--line) transparent;
  min-height: 0;
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
.err {
  color: var(--danger);
  margin: 0;
  font-size: 0.85rem;
}

@media (max-width: 760px) {
  .team-scores {
    grid-template-columns: 1fr;
  }
}
</style>

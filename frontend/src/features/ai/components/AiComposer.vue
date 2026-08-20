<script setup lang="ts">
import { computed, nextTick, ref } from 'vue'
import { watchlistApi, type WatchlistItem } from '../../../api/watchlist'

export type QuickAction = {
  id: string
  label: string
  icon: string
  mode: 'prompt' | 'team'
  needSymbol?: boolean
  template: string
}

const props = defineProps<{
  draft: string
  teamMode: 'fast' | 'deep'
  busy: boolean
  teamBusy: boolean
  teamWeighted: number | null
  quickActions: QuickAction[]
}>()

const emit = defineEmits<{
  'update:draft': [v: string]
  'update:teamMode': [v: 'fast' | 'deep']
  send: []
  applyQuick: [action: QuickAction]
  rememberSymbol: [vt: string]
}>()

const draftEl = ref<HTMLTextAreaElement | null>(null)
const slashMenuOpen = ref(false)
const slashQuery = ref('')
const slashStart = ref(-1)
const watchlistItems = ref<WatchlistItem[]>([])
const watchlistLoading = ref(false)

const filteredWatchlist = computed(() => {
  const q = slashQuery.value.trim().toLowerCase()
  return watchlistItems.value
    .filter((it) => {
      if (!q) return true
      return (
        it.vt_symbol.toLowerCase().includes(q) ||
        (it.name || '').toLowerCase().includes(q) ||
        (it.symbol || '').toLowerCase().includes(q)
      )
    })
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
  const pos = el.selectionStart ?? props.draft.length
  const before = props.draft.slice(0, pos)
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

function onDraftInput(e: Event) {
  emit('update:draft', (e.target as HTMLTextAreaElement).value)
  nextTick(() => syncSlashMenuFromDraft())
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
  const pos = el.selectionStart ?? props.draft.length
  const insert = item.vt_symbol
  const nextDraft = props.draft.slice(0, start) + insert + props.draft.slice(pos)
  emit('update:draft', nextDraft)
  emit('rememberSymbol', item.vt_symbol)
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
    const idx = props.draft.indexOf('/')
    if (idx >= 0) {
      el.setSelectionRange(idx, idx + 1)
      syncSlashMenuFromDraft()
    } else {
      const end = props.draft.length
      el.setSelectionRange(end, end)
    }
  })
}

function focusEnd() {
  nextTick(() => {
    const el = draftEl.value
    if (!el) return
    el.focus()
    const end = props.draft.length
    el.setSelectionRange(end, end)
  })
}

function closeSlash() {
  slashMenuOpen.value = false
}

function toggleMode() {
  emit('update:teamMode', props.teamMode === 'fast' ? 'deep' : 'fast')
}

defineExpose({ focusDraftSlash, focusEnd, closeSlash })
</script>

<template>
  <div class="composer-block">
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
        @click="emit('applyQuick', action)"
      >
        <span class="quick-icon" aria-hidden="true">{{ action.icon }}</span>
        <span>{{ action.label }}</span>
      </button>
    </div>

    <form class="composer" @submit.prevent="emit('send')">
      <div class="draft-wrap">
        <textarea
          ref="draftEl"
          :value="draft"
          rows="2"
          placeholder="有问题，尽管问…"
          @input="onDraftInput"
          @keyup="onDraftKeyup"
          @click="onDraftClick"
          @blur="onDraftBlur"
          @keydown.ctrl.enter.prevent="emit('send')"
          @keydown.escape.prevent="slashMenuOpen = false"
        />
        <div v-if="slashMenuOpen" class="slash-menu" @mousedown.prevent>
          <p class="slash-tip">从自选插入股票代码</p>
          <p v-if="watchlistLoading" class="hint muted">加载自选中…</p>
          <p v-else-if="!filteredWatchlist.length" class="hint muted">无匹配，可继续手输代码</p>
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
            @click="toggleMode"
          >
            <span class="chip-icon" aria-hidden="true">{{ teamMode === 'deep' ? '◈' : '⚡' }}</span>
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
  </div>
</template>

<style scoped>
.composer-block {
  display: grid;
  gap: 10px;
}
.hint {
  margin: 0;
  font-size: 0.75rem;
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


@media (max-width: 600px) {
  .composer-hint {
    display: none;
  }
}

</style>

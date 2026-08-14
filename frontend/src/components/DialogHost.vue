<script setup lang="ts">
import { nextTick, ref, watch } from 'vue'
import { useDialog } from '../lib/dialog'

const { state, settle } = useDialog()
const input = ref('')
const inputEl = ref<HTMLInputElement | null>(null)

watch(
  () => state.current,
  (req) => {
    input.value = req?.kind === 'prompt' ? (req.initialValue ?? '') : ''
    if (req) void nextTick(() => inputEl.value?.focus())
  },
)

function onConfirm() {
  if (!state.current) return
  settle(state.current.kind === 'prompt' ? input.value : true)
}

function onCancel() {
  if (!state.current) return
  settle(state.current.kind === 'prompt' ? null : false)
}
</script>

<template>
  <Teleport to="body">
    <div
      v-if="state.current"
      class="dialog-overlay"
      @click.self="onCancel"
      @keydown.esc="onCancel"
    >
      <div class="dialog" role="dialog" aria-modal="true" :aria-label="state.current.title">
        <h2 class="dialog-title">{{ state.current.title }}</h2>
        <p v-if="state.current.message" class="dialog-message">{{ state.current.message }}</p>
        <input
          v-if="state.current.kind === 'prompt'"
          ref="inputEl"
          v-model="input"
          class="dialog-input"
          :placeholder="state.current.placeholder"
          @keydown.enter="onConfirm"
        />
        <div class="dialog-actions">
          <button type="button" class="btn-ghost" @click="onCancel">
            {{ state.current.cancelText || '取消' }}
          </button>
          <button
            type="button"
            class="btn-primary"
            :class="{ danger: state.current.kind === 'confirm' && state.current.danger }"
            @click="onConfirm"
          >
            {{ state.current.confirmText || '确定' }}
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.dialog-overlay {
  position: fixed;
  inset: 0;
  z-index: 1000;
  display: grid;
  place-items: center;
  background: rgba(0, 0, 0, 0.4);
  padding: 24px;
}
.dialog {
  width: 100%;
  max-width: 400px;
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: 0.875rem;
  box-shadow: var(--shadow-panel);
  padding: 20px;
  display: grid;
  gap: 12px;
}
.dialog-title {
  margin: 0;
  font-size: 1.05rem;
  font-weight: 600;
  color: var(--ink);
}
.dialog-message {
  margin: 0;
  color: var(--ink-muted);
  font-size: 0.875rem;
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-word;
}
.dialog-input {
  width: 100%;
  border-radius: 0.5rem;
  border: 1px solid var(--line);
  background: var(--surface);
  color: var(--ink);
  padding: 0.5rem 0.75rem;
  font-size: 0.875rem;
}
.dialog-input:focus {
  border-color: var(--brand);
  box-shadow: 0 0 0 3px rgba(230, 100, 50, 0.15);
  outline: none;
}
.dialog-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
.btn-primary.danger {
  background: var(--danger);
}
.btn-primary.danger:hover {
  background: #be123c;
}
</style>

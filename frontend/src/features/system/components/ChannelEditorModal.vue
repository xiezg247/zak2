<script setup lang="ts">
defineProps<{
  open: boolean
  saving: boolean
  error: string
  editingId: string
}>()

const formName = defineModel<string>('formName', { required: true })
const formWebhook = defineModel<string>('formWebhook', { required: true })
const formEnabled = defineModel<boolean>('formEnabled', { required: true })

const emit = defineEmits<{
  'update:open': [value: boolean]
  save: []
}>()

function close() {
  emit('update:open', false)
}
</script>

<template>
  <Teleport to="body">
    <Transition name="fade">
      <div v-if="open" class="overlay" @click.self="close">
        <div class="editor" role="dialog" aria-modal="true">
          <h3 class="editor-title">{{ editingId ? '编辑渠道' : '新增渠道' }}</h3>
          <label class="field">
            <span class="field-label">渠道名称</span>
            <input
              v-model="formName"
              class="input-field"
              placeholder="例如：我的飞书群"
              maxlength="40"
            />
          </label>
          <label class="field">
            <span class="field-label">飞书 Webhook 地址</span>
            <input
              v-model="formWebhook"
              class="input-field mono"
              placeholder="https://open.feishu.cn/open-apis/bot/v2/hook/…"
            />
          </label>
          <label class="check-row">
            <input v-model="formEnabled" type="checkbox" />
            <span>启用推送</span>
          </label>
          <p v-if="error" class="err">{{ error }}</p>
          <div class="editor-actions">
            <button type="button" class="ghost" :disabled="saving" @click="close">取消</button>
            <button type="button" class="primary" :disabled="saving" @click="emit('save')">
              {{ saving ? '保存中…' : '保存' }}
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.mono {
  font-family: var(--mono);
}
.overlay {
  position: fixed;
  inset: 0;
  z-index: 1000;
  display: grid;
  place-items: center;
  background: rgba(0, 0, 0, 0.4);
  padding: 24px;
}
.editor {
  width: 100%;
  max-width: 460px;
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: 0.875rem;
  box-shadow: var(--shadow-panel);
  padding: 20px;
  display: grid;
  gap: 14px;
}
.editor-title {
  margin: 0;
  font-size: 1.05rem;
  font-weight: 600;
}
.field {
  display: grid;
  gap: 6px;
}
.field-label {
  font-size: 0.8125rem;
  color: var(--ink-muted);
}
.check-row {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 0.875rem;
  color: var(--ink);
  cursor: pointer;
}
.editor-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
.err {
  color: var(--danger);
}
.input-field {
  border-radius: 0.5rem;
  padding: 0.5rem 0.75rem;
  border: 1px solid var(--line);
  background: var(--bg);
  color: var(--ink);
  font-size: 0.875rem;
}
.primary,
.ghost {
  border-radius: 0.5rem;
  padding: 8px 12px;
  border: 1px solid var(--border);
  cursor: pointer;
  font-size: 0.875rem;
}
.primary {
  background: var(--accent);
  border-color: transparent;
  color: var(--brand-foreground);
  font-weight: 600;
}
.ghost {
  background: var(--bg);
  color: var(--text);
}
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.15s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>

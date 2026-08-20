<script setup lang="ts">
import type { BuiltinRecipe } from '../../../api/screener'

const DAY_OPTIONS = [
  { key: 'mon', label: '周一' },
  { key: 'tue', label: '周二' },
  { key: 'wed', label: '周三' },
  { key: 'thu', label: '周四' },
  { key: 'fri', label: '周五' },
  { key: 'sat', label: '周六' },
  { key: 'sun', label: '周日' },
]

defineProps<{
  open: boolean
  saving: boolean
  error: string
  editingId: number | null
  recipes: BuiltinRecipe[]
}>()

const formName = defineModel<string>('formName', { required: true })
const formRecipe = defineModel<string>('formRecipe', { required: true })
const formDays = defineModel<string[]>('formDays', { required: true })
const formTimes = defineModel<string[]>('formTimes', { required: true })

const emit = defineEmits<{
  'update:open': [value: boolean]
  save: []
  'add-time': []
  'remove-time': [index: number]
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
          <h3 class="editor-title">{{ editingId != null ? '编辑任务' : '新建任务' }}</h3>
          <label class="field">
            <span class="field-label">任务名称</span>
            <input
              v-model="formName"
              class="input-field"
              placeholder="例如：盘中自动选股"
              maxlength="64"
            />
          </label>
          <label class="field">
            <span class="field-label">选股配方</span>
            <select v-model="formRecipe" class="input-field">
              <option v-for="r in recipes" :key="r.recipe_id" :value="r.recipe_id">
                {{ r.name }}
              </option>
            </select>
          </label>
          <div class="field">
            <span class="field-label">每周执行日</span>
            <div class="day-row">
              <label v-for="d in DAY_OPTIONS" :key="d.key" class="day-chip">
                <input v-model="formDays" type="checkbox" :value="d.key" />
                <span>{{ d.label }}</span>
              </label>
            </div>
          </div>
          <div class="field">
            <span class="field-label">执行时刻（每天）</span>
            <div v-for="(_, i) in formTimes" :key="i" class="time-row">
              <input
                v-model="formTimes[i]"
                class="input-field time-input"
                placeholder="HH:MM"
                maxlength="5"
              />
              <button
                type="button"
                class="ghost small"
                :disabled="formTimes.length <= 1"
                @click="emit('remove-time', i)"
              >
                删除
              </button>
            </div>
            <button type="button" class="ghost small" @click="emit('add-time')">+ 添加时刻</button>
          </div>
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
.day-row {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.day-chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  border: 1px solid var(--line);
  border-radius: 999px;
  padding: 4px 10px;
  font-size: 0.8125rem;
  cursor: pointer;
}
.time-row {
  display: flex;
  gap: 8px;
  margin-bottom: 8px;
  align-items: center;
}
.time-input {
  max-width: 120px;
}
.overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.4);
  display: grid;
  place-items: center;
  z-index: 50;
}
.editor {
  width: min(480px, 92vw);
  max-height: 88vh;
  overflow: auto;
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: 0.875rem;
  padding: 20px;
  display: grid;
  gap: 14px;
}
.editor-title {
  margin: 0;
  font-size: 1rem;
}
.field {
  display: grid;
  gap: 6px;
}
.field-label {
  font-size: 0.8125rem;
  font-weight: 600;
  color: var(--ink-muted);
}
.input-field {
  border-radius: 0.5rem;
  padding: 0.5rem 0.75rem;
  border: 1px solid var(--line);
  background: var(--bg);
  color: var(--ink);
  font-size: 0.875rem;
}
.editor-actions {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
}
.err {
  color: var(--danger);
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
.ghost.small {
  padding: 4px 8px;
  font-size: 0.8125rem;
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

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import AppShell from '../components/AppShell.vue'
import { autoScheduleApi, type AutoSchedule } from '../api/autoSchedule'
import { screenerApi, type BuiltinRecipe } from '../api/screener'
import { confirmDialog } from '../lib/dialog'
import { fmtDateTime } from '../lib/format'

const items = ref<AutoSchedule[]>([])
const recipes = ref<BuiltinRecipe[]>([])
const loading = ref(false)
const loaded = ref(false)
const error = ref('')

const bannerMsg = ref('')
const bannerKind = ref<'ok' | 'err'>('ok')

const editorOpen = ref(false)
const editorSaving = ref(false)
const editorErr = ref('')
const editingId = ref<number | null>(null)
const formName = ref('')
const formRecipe = ref('')
const formDays = ref<string[]>(['mon', 'tue', 'wed', 'thu', 'fri'])
const formTimes = ref<string[]>(['09:35'])

const DAY_OPTIONS = [
  { key: 'mon', label: '周一' },
  { key: 'tue', label: '周二' },
  { key: 'wed', label: '周三' },
  { key: 'thu', label: '周四' },
  { key: 'fri', label: '周五' },
  { key: 'sat', label: '周六' },
  { key: 'sun', label: '周日' },
]

const DAY_LABEL: Record<string, string> = Object.fromEntries(
  DAY_OPTIONS.map((d) => [d.key, d.label]),
)

function banner(kind: 'ok' | 'err', msg: string) {
  bannerKind.value = kind
  bannerMsg.value = msg
}

function recipeName(recipeId: string): string {
  return recipes.value.find((r) => r.recipe_id === recipeId)?.name || recipeId
}

function scheduleText(t: AutoSchedule): string {
  const dayText = t.days_of_week
    .split(',')
    .map((d) => DAY_LABEL[d] || d)
    .join('·')
  return `${dayText} ${t.times.join('、')}`
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    items.value = (await autoScheduleApi.list()).items
    loaded.value = true
  } catch (e) {
    error.value = e instanceof Error ? e.message : '任务列表加载失败'
  } finally {
    loading.value = false
  }
}

async function loadRecipes() {
  try {
    recipes.value = (await screenerApi.builtinRecipes()).filter((r) => r.implemented)
    if (!formRecipe.value && recipes.value.length) {
      formRecipe.value = recipes.value[0].recipe_id
    }
  } catch {
    /* 配方加载失败静默，保存时后端会校验 */
  }
}

function openCreate() {
  editingId.value = null
  formName.value = ''
  formRecipe.value = recipes.value[0]?.recipe_id || ''
  formDays.value = ['mon', 'tue', 'wed', 'thu', 'fri']
  formTimes.value = ['09:35']
  editorErr.value = ''
  editorOpen.value = true
}

function openEdit(t: AutoSchedule) {
  editingId.value = t.id
  formName.value = t.name
  formRecipe.value = t.recipe_id
  formDays.value = t.days_of_week.split(',')
  formTimes.value = [...t.times]
  editorErr.value = ''
  editorOpen.value = true
}

function addTimeRow() {
  formTimes.value = [...formTimes.value, '']
}

function removeTimeRow(index: number) {
  formTimes.value = formTimes.value.filter((_, i) => i !== index)
}

async function saveEditor() {
  const name = formName.value.trim()
  const days = formDays.value.join(',')
  const times = formTimes.value
    .map((t) => t.trim())
    .filter((t) => t !== '')
    .sort()
  const deduped = [...new Set(times)]
  if (!name) {
    editorErr.value = '请填写任务名称'
    return
  }
  if (formDays.value.length === 0) {
    editorErr.value = '请至少选择一天'
    return
  }
  if (deduped.length === 0) {
    editorErr.value = '请至少填写一个执行时刻'
    return
  }
  if (deduped.some((t) => !/^([01]\d|2[0-3]):[0-5]\d$/.test(t))) {
    editorErr.value = '时刻格式应为 HH:MM，如 09:35'
    return
  }
  editorSaving.value = true
  editorErr.value = ''
  const body = { name, recipe_id: formRecipe.value, days_of_week: days, times: deduped }
  try {
    if (editingId.value != null) {
      await autoScheduleApi.update(editingId.value, body)
    } else {
      await autoScheduleApi.create(body)
    }
    editorOpen.value = false
    banner('ok', editingId.value != null ? '任务已更新' : '任务已创建')
    void load()
  } catch (e) {
    editorErr.value = e instanceof Error ? e.message : '保存失败'
  } finally {
    editorSaving.value = false
  }
}

async function toggleEnabled(t: AutoSchedule) {
  try {
    await autoScheduleApi.setEnabled(t.id, !t.enabled)
    void load()
  } catch (e) {
    banner('err', e instanceof Error ? e.message : '切换失败')
  }
}

async function removeTask(t: AutoSchedule) {
  const ok = await confirmDialog({
    title: '删除任务',
    message: `确认删除「${t.name}」？删除后不再定时执行。`,
    confirmText: '删除',
    danger: true,
  })
  if (!ok) return
  try {
    await autoScheduleApi.remove(t.id)
    banner('ok', '任务已删除')
    void load()
  } catch (e) {
    banner('err', e instanceof Error ? e.message : '删除失败')
  }
}

onMounted(() => {
  void loadRecipes()
  void load()
})

const empty = computed(
  () => loaded.value && !loading.value && !error.value && items.value.length === 0,
)
</script>

<template>
  <AppShell
    title="自动任务"
    subtitle="创建选股任务：选择配方与执行时刻，到点自动跑选股并推送已启用渠道。"
    active="auto-schedule"
  >
    <div class="page">
      <div class="toolbar">
        <div>
          <h2>我的自动任务</h2>
          <p class="muted">按用户隔离；任务按「星期 + 时刻」分钟级触发，不补跑错过的时刻。</p>
        </div>
        <div class="actions">
          <button type="button" class="primary" @click="openCreate">+ 新建任务</button>
          <button type="button" class="ghost" :disabled="loading" @click="load">
            {{ loading ? '加载中…' : '刷新' }}
          </button>
        </div>
      </div>

      <Transition name="fade">
        <div v-if="bannerMsg" class="banner" :class="bannerKind">
          {{ bannerMsg }}
          <button type="button" class="banner-close" aria-label="关闭" @click="bannerMsg = ''">
            ×
          </button>
        </div>
      </Transition>

      <p v-if="loading && !loaded" class="muted">加载任务列表…</p>
      <p v-else-if="error" class="err">{{ error }}</p>
      <template v-else>
        <div v-if="items.length" class="task-list">
          <div v-for="t in items" :key="t.id" class="task-card" :class="{ off: !t.enabled }">
            <div class="card-head">
              <div class="card-title">
                <span class="name">{{ t.name }}</span>
                <span class="badge">{{ recipeName(t.recipe_id) }}</span>
                <span v-if="!t.enabled" class="badge off">已停用</span>
              </div>
              <label class="switch" :title="t.enabled ? '停用' : '启用'">
                <input type="checkbox" :checked="t.enabled" @change="toggleEnabled(t)" />
                <span class="slider" />
              </label>
            </div>
            <div class="schedule">{{ scheduleText(t) }}</div>
            <div class="last-run">
              <template v-if="t.last_run_at">
                <span :class="t.last_success === false ? 'err' : t.last_success ? 'ok-text' : ''">
                  {{ t.last_success === false ? '失败' : t.last_success ? '成功' : '—' }}
                </span>
                <span class="muted">· {{ fmtDateTime(t.last_run_at) }}</span>
                <div v-if="t.last_message" class="muted msg">{{ t.last_message }}</div>
              </template>
              <span v-else class="muted">尚未执行</span>
            </div>
            <div class="card-actions">
              <button type="button" class="ghost" @click="openEdit(t)">编辑</button>
              <button type="button" class="ghost danger" @click="removeTask(t)">删除</button>
            </div>
          </div>
        </div>
        <div v-else-if="empty" class="empty">
          <p>还没有创建任何自动任务。</p>
          <button type="button" class="primary" @click="openCreate">+ 新建任务</button>
        </div>
      </template>
    </div>
  </AppShell>

  <Teleport to="body">
    <Transition name="fade">
      <div v-if="editorOpen" class="overlay" @click.self="editorOpen = false">
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
                @click="removeTimeRow(i)"
              >
                删除
              </button>
            </div>
            <button type="button" class="ghost small" @click="addTimeRow">+ 添加时刻</button>
          </div>
          <p v-if="editorErr" class="err">{{ editorErr }}</p>
          <div class="editor-actions">
            <button
              type="button"
              class="ghost"
              :disabled="editorSaving"
              @click="editorOpen = false"
            >
              取消
            </button>
            <button type="button" class="primary" :disabled="editorSaving" @click="saveEditor">
              {{ editorSaving ? '保存中…' : '保存' }}
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.page {
  display: grid;
  gap: 16px;
}
.toolbar h2 {
  margin: 0;
  font-size: 1rem;
}
.actions {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
}
.banner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  border-radius: 0.625rem;
  padding: 0.6rem 0.85rem;
  font-size: 0.875rem;
}
.banner.ok {
  background: #f0fdf4;
  color: var(--ok);
  border: 1px solid #bbf7d0;
}
.banner.err {
  background: #fef2f2;
  color: var(--danger);
  border: 1px solid #fecaca;
}
.banner-close {
  border: none;
  background: transparent;
  color: inherit;
  font-size: 1rem;
  line-height: 1;
  padding: 2px 4px;
  border-radius: 0.375rem;
}
.task-list {
  display: grid;
  gap: 12px;
}
.task-card {
  border: 1px solid var(--line);
  border-radius: 0.75rem;
  background: var(--surface);
  padding: 12px 14px;
  display: grid;
  gap: 8px;
}
.task-card.off {
  opacity: 0.6;
}
.card-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
}
.card-title {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}
.name {
  font-weight: 600;
}
.badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 0.75rem;
  font-weight: 600;
  background: #eef2ff;
  color: #4338ca;
}
.badge.off {
  background: #f1f5f9;
  color: #64748b;
}
.schedule {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 0.875rem;
}
.last-run {
  font-size: 0.8125rem;
}
.msg {
  margin-top: 2px;
  word-break: break-all;
}
.card-actions {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
}
.muted {
  color: var(--muted);
  font-size: 0.78rem;
}
.err {
  color: var(--danger);
}
.ok-text {
  color: var(--ok);
}
.empty {
  border: 1px dashed var(--line);
  border-radius: 0.75rem;
  padding: 40px;
  text-align: center;
  color: var(--muted);
  display: grid;
  gap: 12px;
  justify-items: center;
}
.switch {
  position: relative;
  display: inline-flex;
  cursor: pointer;
}
.switch input {
  opacity: 0;
  width: 0;
  height: 0;
}
.slider {
  width: 40px;
  height: 22px;
  border-radius: 999px;
  background: var(--line);
  position: relative;
  transition: background 0.2s ease;
}
.slider::before {
  content: '';
  position: absolute;
  width: 18px;
  height: 18px;
  border-radius: 999px;
  background: #fff;
  top: 2px;
  left: 2px;
  transition: transform 0.2s ease;
}
.switch input:checked + .slider {
  background: var(--ok);
}
.switch input:checked + .slider::before {
  transform: translateX(18px);
}
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
.ghost.danger {
  color: var(--danger);
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

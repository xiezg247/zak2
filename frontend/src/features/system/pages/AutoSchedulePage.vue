<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import AppShell from '../../../components/AppShell.vue'
import { autoScheduleApi, type AutoSchedule } from '../../../api/autoSchedule'
import { screenerApi, type BuiltinRecipe } from '../../../api/screener'
import { confirmDialog } from '../../../lib/dialog'
import AutoScheduleTaskList from '../components/AutoScheduleTaskList.vue'
import AutoScheduleEditorModal from '../components/AutoScheduleEditorModal.vue'

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

function banner(kind: 'ok' | 'err', msg: string) {
  bannerKind.value = kind
  bannerMsg.value = msg
}

function recipeName(recipeId: string): string {
  return recipes.value.find((r) => r.recipe_id === recipeId)?.name || recipeId
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
    <AutoScheduleTaskList
      :items="items"
      :loading="loading"
      :loaded="loaded"
      :empty="empty"
      :error="error"
      :banner-msg="bannerMsg"
      :banner-kind="bannerKind"
      :recipe-name="recipeName"
      @create="openCreate"
      @refresh="load"
      @edit="openEdit"
      @remove="removeTask"
      @toggle="toggleEnabled"
      @clear-banner="bannerMsg = ''"
    />
  </AppShell>

  <AutoScheduleEditorModal
    v-model:open="editorOpen"
    v-model:form-name="formName"
    v-model:form-recipe="formRecipe"
    v-model:form-days="formDays"
    v-model:form-times="formTimes"
    :saving="editorSaving"
    :error="editorErr"
    :editing-id="editingId"
    :recipes="recipes"
    @save="saveEditor"
    @add-time="addTimeRow"
    @remove-time="removeTimeRow"
  />
</template>

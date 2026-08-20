<script setup lang="ts">
import type { AutoSchedule } from '../../../api/autoSchedule'
import { fmtDateTime } from '../../../lib/format'

const DAY_LABEL: Record<string, string> = {
  mon: '周一',
  tue: '周二',
  wed: '周三',
  thu: '周四',
  fri: '周五',
  sat: '周六',
  sun: '周日',
}

defineProps<{
  items: AutoSchedule[]
  loading: boolean
  loaded: boolean
  empty: boolean
  error: string
  bannerMsg: string
  bannerKind: 'ok' | 'err'
  recipeName: (recipeId: string) => string
}>()

const emit = defineEmits<{
  create: []
  refresh: []
  edit: [task: AutoSchedule]
  remove: [task: AutoSchedule]
  toggle: [task: AutoSchedule]
  'clear-banner': []
}>()

function scheduleText(t: AutoSchedule): string {
  const dayText = t.days_of_week
    .split(',')
    .map((d) => DAY_LABEL[d] || d)
    .join('·')
  return `${dayText} ${t.times.join('、')}`
}
</script>

<template>
  <div class="page">
    <div class="toolbar">
      <div>
        <h2>我的自动任务</h2>
        <p class="muted">按用户隔离；任务按「星期 + 时刻」分钟级触发，不补跑错过的时刻。</p>
      </div>
      <div class="actions">
        <button type="button" class="primary" @click="emit('create')">+ 新建任务</button>
        <button type="button" class="ghost" :disabled="loading" @click="emit('refresh')">
          {{ loading ? '加载中…' : '刷新' }}
        </button>
      </div>
    </div>

    <Transition name="fade">
      <div v-if="bannerMsg" class="banner" :class="bannerKind">
        {{ bannerMsg }}
        <button type="button" class="banner-close" aria-label="关闭" @click="emit('clear-banner')">
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
              <input type="checkbox" :checked="t.enabled" @change="emit('toggle', t)" />
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
            <button type="button" class="ghost" @click="emit('edit', t)">编辑</button>
            <button type="button" class="ghost danger" @click="emit('remove', t)">删除</button>
          </div>
        </div>
      </div>
      <div v-else-if="empty" class="empty">
        <p>还没有创建任何自动任务。</p>
        <button type="button" class="primary" @click="emit('create')">+ 新建任务</button>
      </div>
    </template>
  </div>
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

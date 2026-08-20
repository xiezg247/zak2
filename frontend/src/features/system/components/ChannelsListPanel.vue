<script setup lang="ts">
import type { Channel } from '../../../api/channels'

defineProps<{
  items: Channel[]
  loading: boolean
  loaded: boolean
  empty: boolean
  error: string
  bannerMsg: string
  bannerKind: 'ok' | 'err'
  testingId: string
}>()

const emit = defineEmits<{
  create: []
  refresh: []
  edit: [ch: Channel]
  remove: [ch: Channel]
  toggle: [ch: Channel]
  test: [ch: Channel]
  'clear-banner': []
}>()

function maskWebhook(url: string): string {
  if (url.length <= 32) return url
  return `${url.slice(0, 28)}…${url.slice(-6)}`
}
</script>

<template>
  <div class="page">
    <div class="toolbar">
      <div>
        <h2>推送渠道</h2>
        <p class="muted">渠道按用户隔离，可添加多个；启用后接收选股结果推送。</p>
      </div>
      <div class="actions">
        <button type="button" class="primary" @click="emit('create')">+ 新增渠道</button>
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

    <p v-if="loading && !loaded" class="muted">加载渠道列表…</p>
    <p v-else-if="error" class="err">{{ error }}</p>
    <template v-else>
      <div v-if="items.length" class="channel-grid">
        <div v-for="ch in items" :key="ch.id" class="channel-card" :class="{ off: !ch.enabled }">
          <div class="card-head">
            <div class="card-title">
              <span class="name">{{ ch.name }}</span>
              <span class="badge">飞书</span>
              <span v-if="!ch.enabled" class="badge off">已停用</span>
            </div>
            <label class="switch" :title="ch.enabled ? '停用' : '启用'">
              <input type="checkbox" :checked="ch.enabled" @change="emit('toggle', ch)" />
              <span class="slider" />
            </label>
          </div>
          <div class="webhook mono" :title="ch.webhook_url">
            {{ maskWebhook(ch.webhook_url) }}
          </div>
          <div class="card-actions">
            <button
              type="button"
              class="ghost"
              :disabled="testingId !== ''"
              @click="emit('test', ch)"
            >
              {{ testingId === ch.id ? '发送中…' : '测试' }}
            </button>
            <button type="button" class="ghost" @click="emit('edit', ch)">编辑</button>
            <button type="button" class="ghost danger" @click="emit('remove', ch)">删除</button>
          </div>
        </div>
      </div>
      <div v-else-if="empty" class="empty">
        <p>还没有接入任何消息渠道。</p>
        <button type="button" class="primary" @click="emit('create')">+ 新增渠道</button>
      </div>
    </template>

    <div class="hint">
      <p>
        接入步骤：在飞书群中添加「自定义机器人」→ 复制 Webhook 地址 → 填入上方新增表单 →
        点「测试」验证。
      </p>
    </div>
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
.banner-close:hover {
  background: rgba(0, 0, 0, 0.06);
}
.channel-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 14px;
}
.channel-card {
  border: 1px solid var(--line);
  border-radius: 0.75rem;
  background: var(--surface);
  box-shadow: var(--shadow-card);
  padding: 14px 16px;
  display: grid;
  gap: 10px;
}
.channel-card.off {
  opacity: 0.65;
}
.card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}
.card-title {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  min-width: 0;
}
.name {
  font-weight: 600;
  font-size: 0.95rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.badge {
  border-radius: 999px;
  background: var(--brand-light);
  color: var(--brand);
  border: 1px solid var(--brand-soft);
  font-size: 0.72rem;
  padding: 0.1rem 0.5rem;
  flex-shrink: 0;
}
.badge.off {
  background: var(--surface-muted);
  color: var(--ink-muted);
  border-color: var(--line);
}
.switch {
  position: relative;
  display: inline-block;
  width: 38px;
  height: 22px;
  flex-shrink: 0;
  cursor: pointer;
}
.switch input {
  opacity: 0;
  width: 0;
  height: 0;
  position: absolute;
}
.slider {
  position: absolute;
  inset: 0;
  border-radius: 999px;
  background: var(--line);
  transition: background 0.15s ease;
}
.slider::before {
  content: '';
  position: absolute;
  width: 16px;
  height: 16px;
  left: 3px;
  top: 3px;
  border-radius: 999px;
  background: #fff;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.2);
  transition: transform 0.15s ease;
}
.switch input:checked + .slider {
  background: var(--brand);
}
.switch input:checked + .slider::before {
  transform: translateX(16px);
}
.webhook {
  font-size: 0.78rem;
  color: var(--ink-muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  word-break: break-all;
}
.card-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.ghost.danger {
  color: var(--danger);
}
.ghost.danger:hover {
  background: #fef2f2;
  border-color: #fecaca;
  color: var(--danger);
}
.empty {
  border: 1px dashed var(--line);
  border-radius: 0.75rem;
  padding: 36px 16px;
  display: grid;
  place-items: center;
  gap: 12px;
  color: var(--ink-muted);
  font-size: 0.875rem;
}
.hint {
  border-radius: 0.625rem;
  background: var(--surface);
  border: 1px solid var(--line);
  padding: 10px 14px;
  font-size: 0.78rem;
  color: var(--ink-muted);
}
.hint p {
  margin: 0;
  line-height: 1.6;
}
.mono {
  font-family: var(--mono);
}
.muted {
  color: var(--muted);
  font-size: 0.78rem;
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
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.15s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>

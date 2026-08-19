<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import AppShell from '../components/AppShell.vue'
import { channelApi, type Channel } from '../api/channels'
import { confirmDialog } from '../lib/dialog'

const items = ref<Channel[]>([])
const loading = ref(false)
const loaded = ref(false)
const error = ref('')

const bannerMsg = ref('')
const bannerKind = ref<'ok' | 'err'>('ok')

const editorOpen = ref(false)
const editorSaving = ref(false)
const editorErr = ref('')
const editingId = ref('')
const formName = ref('')
const formWebhook = ref('')
const formEnabled = ref(true)

const testingId = ref('')

function banner(kind: 'ok' | 'err', msg: string) {
  bannerKind.value = kind
  bannerMsg.value = msg
}

function maskWebhook(url: string): string {
  if (url.length <= 32) return url
  return `${url.slice(0, 28)}…${url.slice(-6)}`
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const out = await channelApi.list()
    items.value = out.items
    loaded.value = true
  } catch (e) {
    error.value = e instanceof Error ? e.message : '渠道列表加载失败'
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editingId.value = ''
  formName.value = ''
  formWebhook.value = ''
  formEnabled.value = true
  editorErr.value = ''
  editorOpen.value = true
}

function openEdit(ch: Channel) {
  editingId.value = ch.id
  formName.value = ch.name
  formWebhook.value = ch.webhook_url
  formEnabled.value = ch.enabled
  editorErr.value = ''
  editorOpen.value = true
}

async function saveEditor() {
  const name = formName.value.trim()
  const webhook = formWebhook.value.trim()
  if (!name) {
    editorErr.value = '请填写渠道名称'
    return
  }
  if (!webhook) {
    editorErr.value = '请填写飞书 Webhook 地址'
    return
  }
  editorSaving.value = true
  editorErr.value = ''
  try {
    if (editingId.value) {
      await channelApi.update(editingId.value, {
        name,
        webhook_url: webhook,
        enabled: formEnabled.value,
      })
    } else {
      await channelApi.create({ name, webhook_url: webhook, enabled: formEnabled.value })
    }
    editorOpen.value = false
    banner('ok', editingId.value ? '渠道已更新' : '渠道已添加')
    void load()
  } catch (e) {
    editorErr.value = e instanceof Error ? e.message : '保存失败'
  } finally {
    editorSaving.value = false
  }
}

async function toggleEnabled(ch: Channel) {
  try {
    await channelApi.update(ch.id, { enabled: !ch.enabled })
    void load()
  } catch (e) {
    banner('err', e instanceof Error ? e.message : '切换失败')
  }
}

async function testChannel(ch: Channel) {
  testingId.value = ch.id
  bannerMsg.value = ''
  try {
    const out = await channelApi.test(ch.id)
    banner(out.ok ? 'ok' : 'err', out.message)
  } catch (e) {
    banner('err', e instanceof Error ? e.message : '测试发送失败')
  } finally {
    testingId.value = ''
  }
}

async function removeChannel(ch: Channel) {
  const ok = await confirmDialog({
    title: '删除渠道',
    message: `确认删除「${ch.name}」？删除后不再向该渠道推送消息。`,
    confirmText: '删除',
    danger: true,
  })
  if (!ok) return
  try {
    await channelApi.remove(ch.id)
    banner('ok', '渠道已删除')
    void load()
  } catch (e) {
    banner('err', e instanceof Error ? e.message : '删除失败')
  }
}

onMounted(() => {
  void load()
})

const empty = computed(
  () => loaded.value && !loading.value && !error.value && items.value.length === 0,
)
</script>

<template>
  <AppShell
    title="消息渠道"
    subtitle="接入飞书自定义机器人，选股/盘后结果将自动推送到已启用渠道。"
    active="channels"
  >
    <div class="page">
      <div class="toolbar">
        <div>
          <h2>推送渠道</h2>
          <p class="muted">渠道按用户隔离，可添加多个；启用后接收选股结果推送。</p>
        </div>
        <div class="actions">
          <button type="button" class="primary" @click="openCreate">+ 新增渠道</button>
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
                <input type="checkbox" :checked="ch.enabled" @change="toggleEnabled(ch)" />
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
                @click="testChannel(ch)"
              >
                {{ testingId === ch.id ? '发送中…' : '测试' }}
              </button>
              <button type="button" class="ghost" @click="openEdit(ch)">编辑</button>
              <button type="button" class="ghost danger" @click="removeChannel(ch)">删除</button>
            </div>
          </div>
        </div>
        <div v-else-if="empty" class="empty">
          <p>还没有接入任何消息渠道。</p>
          <button type="button" class="primary" @click="openCreate">+ 新增渠道</button>
        </div>
      </template>

      <div class="hint">
        <p>
          接入步骤：在飞书群中添加「自定义机器人」→ 复制 Webhook 地址 → 填入上方新增表单 →
          点「测试」验证。
        </p>
      </div>
    </div>
  </AppShell>

  <Teleport to="body">
    <Transition name="fade">
      <div v-if="editorOpen" class="overlay" @click.self="editorOpen = false">
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
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.15s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import AppShell from '../../../components/AppShell.vue'
import { channelApi, type Channel } from '../../../api/channels'
import { confirmDialog } from '../../../lib/dialog'
import ChannelsListPanel from '../components/ChannelsListPanel.vue'
import ChannelEditorModal from '../components/ChannelEditorModal.vue'

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
    <ChannelsListPanel
      :items="items"
      :loading="loading"
      :loaded="loaded"
      :empty="empty"
      :error="error"
      :banner-msg="bannerMsg"
      :banner-kind="bannerKind"
      :testing-id="testingId"
      @create="openCreate"
      @refresh="load"
      @edit="openEdit"
      @remove="removeChannel"
      @toggle="toggleEnabled"
      @test="testChannel"
      @clear-banner="bannerMsg = ''"
    />
  </AppShell>

  <ChannelEditorModal
    v-model:open="editorOpen"
    v-model:form-name="formName"
    v-model:form-webhook="formWebhook"
    v-model:form-enabled="formEnabled"
    :saving="editorSaving"
    :error="editorErr"
    :editing-id="editingId"
    @save="saveEditor"
  />
</template>

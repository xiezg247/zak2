<script setup lang="ts">
import { onMounted, ref } from 'vue'
import AppShell from '../components/AppShell.vue'
import { fmtDateTime } from '../lib/format'
import { watchlistApi, type NotifyLogItem } from '../api/watchlist'

const items = ref<NotifyLogItem[]>([])
const expandedId = ref('')
const loading = ref(false)
const loaded = ref(false)
const error = ref('')

function prettyPayload(payload: Record<string, unknown>): string {
  try {
    return JSON.stringify(payload, null, 2)
  } catch {
    return String(payload)
  }
}

function notifyStatusClass(status: string): string {
  const s = status.trim().toLowerCase()
  if (s === 'ok' || s === 'success') return ''
  return 'warn'
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const out = await watchlistApi.notifyLog()
    items.value = out.items
    loaded.value = true
  } catch (e) {
    error.value = e instanceof Error ? e.message : '通知投递记录加载失败'
  } finally {
    loading.value = false
  }
}

function toggleRow(id: string) {
  expandedId.value = expandedId.value === id ? '' : id
}

onMounted(() => {
  void load()
})
</script>

<template>
  <AppShell title="通知" subtitle="风险预警等通知的渠道投递状态，只读排障用。" active="notify">
    <div class="page">
      <section class="panel">
        <div class="toolbar">
          <div>
            <h2>通知投递记录</h2>
            <p class="muted">风险预警等通知的渠道投递状态，只读排障用。</p>
          </div>
          <div class="actions">
            <button type="button" class="ghost" :disabled="loading" @click="load">
              {{ loading ? '加载中…' : '刷新' }}
            </button>
          </div>
        </div>
        <p v-if="loading && !loaded" class="muted">加载通知投递记录…</p>
        <p v-else-if="error" class="err">{{ error }}</p>
        <template v-else>
          <table v-if="items.length">
            <thead>
              <tr>
                <th>时间</th>
                <th>事件</th>
                <th>渠道</th>
                <th>状态</th>
                <th>错误</th>
              </tr>
            </thead>
            <tbody>
              <template v-for="row in items" :key="row.id">
                <tr :class="{ on: expandedId === row.id }" @click="toggleRow(row.id)">
                  <td class="mono">{{ fmtDateTime(row.created_at) || '—' }}</td>
                  <td>{{ row.event_type || '—' }}</td>
                  <td>{{ row.channel || '—' }}</td>
                  <td :class="notifyStatusClass(row.status)">{{ row.status || '—' }}</td>
                  <td class="clip">{{ row.error || '—' }}</td>
                </tr>
                <tr v-if="expandedId === row.id" class="payload-row">
                  <td colspan="5">
                    <pre class="payload">{{ prettyPayload(row.payload) }}</pre>
                  </td>
                </tr>
              </template>
            </tbody>
          </table>
          <p v-else class="muted tip">暂无通知投递记录</p>
        </template>
      </section>
    </div>
  </AppShell>
</template>

<style scoped>
.page {
  display: grid;
  gap: 16px;
}
.panel {
  border: 1px solid var(--line);
  border-radius: 0.75rem;
  background: var(--surface);
  box-shadow: var(--shadow-card);
  padding: 14px 16px;
  overflow: auto;
}
.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  margin-bottom: 10px;
  flex-wrap: wrap;
}
.toolbar h2 {
  margin: 0;
  font-size: 1rem;
}
.actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  align-items: center;
}
table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.88rem;
}
th,
td {
  text-align: left;
  padding: 8px 6px;
  border-bottom: 1px solid var(--border);
  vertical-align: top;
}
th {
  color: var(--muted);
  font-weight: 600;
}
tr:hover td {
  background: var(--surface-muted);
  cursor: pointer;
}
tr.on td {
  background: var(--brand-light);
}
tr.on:hover td {
  background: var(--brand-light);
}
.payload-row {
  cursor: default !important;
}
.payload-row td {
  white-space: normal;
  background: var(--surface-muted);
  padding: 8px 10px;
}
.payload {
  margin: 0;
  max-height: 200px;
  overflow: auto;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 0.75rem;
  color: var(--muted);
  white-space: pre-wrap;
  word-break: break-word;
}
.clip {
  max-width: 260px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.muted {
  color: var(--muted);
  font-size: 0.78rem;
}
.mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  white-space: nowrap;
}
.err {
  color: var(--danger);
  margin: 0;
}
.warn {
  color: var(--danger);
}
.ghost {
  border-radius: 0.5rem;
  padding: 8px 12px;
  border: 1px solid var(--border);
  cursor: pointer;
  background: var(--bg);
  color: var(--text);
}
.tip {
  cursor: help;
}
</style>

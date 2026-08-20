<script setup lang="ts">
import { fmtDateTime } from '../../../lib/format'
import type { OpsJob } from '../../../api/ops'

const STATUS_LABEL: Record<string, string> = {
  pending: '排队中',
  running: '运行中',
  success: '成功',
  failed: '失败',
}

defineProps<{
  recentJobs: OpsJob[]
  jobNameFor: (kind: string) => string
}>()

const emit = defineEmits<{
  refresh: []
}>()

function statusLabel(status: string): string {
  return STATUS_LABEL[status] || status
}
</script>

<template>
  <section class="panel">
    <div class="toolbar">
      <div>
        <h2>任务进度</h2>
        <p class="muted">异步执行的 job 状态与进度，每 3 秒自动刷新</p>
      </div>
      <button type="button" class="ghost" @click="emit('refresh')">刷新</button>
    </div>
    <table v-if="recentJobs.length">
      <thead>
        <tr>
          <th>任务</th>
          <th>状态</th>
          <th>进度</th>
          <th>提交时间</th>
          <th>结果</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="job in recentJobs" :key="job.id">
          <td>
            <div class="name">{{ jobNameFor(job.kind) }}</div>
            <div class="muted">{{ job.id }}</div>
          </td>
          <td>
            <span class="badge" :class="job.status">{{ statusLabel(job.status) }}</span>
          </td>
          <td>
            <div class="progress">
              <span
                class="progress-fill"
                :style="{ width: Math.round(job.progress * 100) + '%' }"
              ></span>
            </div>
            <div class="muted">{{ Math.round(job.progress * 100) }}%</div>
          </td>
          <td class="mono">{{ fmtDateTime(job.created_at) }}</td>
          <td>
            <div v-if="job.error" class="err">{{ job.error }}</div>
            <div v-else class="muted">{{ job.result_ref || '—' }}</div>
          </td>
        </tr>
      </tbody>
    </table>
    <p v-else class="muted">暂无任务记录</p>
  </section>
</template>

<style scoped>
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
.name {
  font-weight: 600;
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
.ghost {
  border-radius: 0.5rem;
  padding: 8px 12px;
  border: 1px solid var(--border);
  cursor: pointer;
  background: var(--bg);
  color: var(--text);
}
.badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 0.75rem;
  font-weight: 600;
}
.badge.pending {
  background: #fef3c7;
  color: #92400e;
}
.badge.running {
  background: #dbeafe;
  color: #1d4ed8;
}
.badge.success {
  background: #ecfdf5;
  color: #166534;
}
.badge.failed {
  background: #fee2e2;
  color: #991b1b;
}
.progress {
  width: 120px;
  height: 6px;
  background: var(--border);
  border-radius: 999px;
  overflow: hidden;
}
.progress-fill {
  display: block;
  height: 100%;
  background: var(--accent);
  transition: width 0.3s ease;
}
</style>

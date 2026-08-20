<script setup lang="ts">
import { fmtDateTime } from '../../../lib/format'
import type { SchedulerJob } from '../../../api/ops'
import { KIND_TITLE, type JobFilter, type JobGroup } from '../opsJobGroups'

defineProps<{
  jobGroups: JobGroup[]
  busy: string
}>()

const jobFilter = defineModel<JobFilter>('jobFilter', { required: true })

const emit = defineEmits<{
  refresh: []
  toggle: [job: SchedulerJob]
  run: [jobId: string, sync: boolean]
}>()

function scheduleText(j: SchedulerJob) {
  if (
    j.interval_seconds &&
    (j.job_id === 'collect_quotes' ||
      j.job_id === 'enrich_market_quotes' ||
      j.job_id === 'warm_radar_card_snapshots')
  ) {
    return `每 ${j.interval_seconds}s`
  }
  const m = String(j.cron_minute ?? 0).padStart(2, '0')
  const d = j.cron_day_of_week || 'mon-fri'
  if (j.cron_hours) {
    return `${d} ${j.cron_hours}:${m}`
  }
  const h = j.cron_hour ?? '-'
  return `${d} ${h}:${m}`
}
</script>

<template>
  <section class="panel">
    <div class="toolbar">
      <div>
        <h2>定时任务</h2>
        <p class="muted">
          内嵌调度覆盖全部可跑 job；盘中/盘后选股定时需配置环境变量 SCHEDULER_SCREEN_USER_ID ·
          预热情绪周期写入短 TTL 缓存 · B 站同步需 BILIBILI_COOKIES
        </p>
      </div>
      <div class="actions">
        <select v-model="jobFilter" class="filter">
          <option value="all">全部</option>
          <option value="runnable">可跑</option>
          <option value="process">独立进程</option>
          <option value="planned">未实现</option>
        </select>
        <button type="button" class="ghost" :disabled="!!busy" @click="emit('refresh')">
          刷新
        </button>
        <button
          type="button"
          class="ghost"
          :disabled="!!busy"
          @click="emit('run', 'sync_trade_calendar', true)"
        >
          同步日历
        </button>
        <button
          type="button"
          class="ghost"
          :disabled="!!busy"
          @click="emit('run', 'sync_sector_flow_daily', true)"
        >
          同步板块资金
        </button>
        <button
          type="button"
          class="ghost"
          :disabled="!!busy"
          @click="emit('run', 'screen_intraday', true)"
        >
          盘中选股
        </button>
        <button
          type="button"
          class="ghost"
          :disabled="!!busy"
          @click="emit('run', 'screen_post_close', true)"
        >
          盘后选股
        </button>
        <button
          type="button"
          class="ghost"
          :disabled="!!busy"
          @click="emit('run', 'warm_market_summary', true)"
        >
          {{ busy === 'warm_market_summary' ? '提交中…' : '预热情绪周期' }}
        </button>
        <button
          type="button"
          class="ghost"
          :disabled="!!busy"
          @click="emit('run', 'sync_bilibili_feed', true)"
        >
          {{ busy === 'sync_bilibili_feed' ? '提交中…' : 'B站订阅同步' }}
        </button>
        <button
          type="button"
          class="primary"
          :disabled="!!busy"
          @click="emit('run', 'purge_stale_cache', true)"
        >
          {{ busy === 'purge_stale_cache' ? '清理中…' : '清理 cache' }}
        </button>
      </div>
    </div>
    <table>
      <thead>
        <tr>
          <th>任务</th>
          <th>启用</th>
          <th>调度</th>
          <th>上次运行</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        <template v-for="g in jobGroups" :key="g.kind">
          <tr class="section">
            <td colspan="5">
              <strong>{{ g.title }}</strong
              >· {{ g.items.length }}
            </td>
          </tr>
          <tr v-for="j in g.items" :key="j.job_id">
            <td>
              <div class="name">{{ j.name }}</div>
              <div class="muted">{{ j.job_id }} · {{ j.description }}</div>
            </td>
            <td>
              <button
                type="button"
                class="toggle"
                :class="{ on: j.enabled }"
                :disabled="busy === j.job_id || (j.job_kind !== 'runnable' && !j.enabled)"
                @click="emit('toggle', j)"
              >
                {{ j.enabled ? '开' : '关' }}
              </button>
            </td>
            <td class="mono">{{ scheduleText(j) }}</td>
            <td>
              <template v-if="j.last_run">
                <div :class="j.last_run.last_success === false ? 'err' : ''">
                  {{
                    j.last_run.last_success === false
                      ? '失败'
                      : j.last_run.last_success
                        ? '成功'
                        : '—'
                  }}
                  · {{ fmtDateTime(j.last_run.last_run_at) }}
                </div>
                <div class="muted">{{ j.last_run.last_message }}</div>
              </template>
              <span v-else class="muted">无记录</span>
            </td>
            <td>
              <button
                v-if="j.job_kind === 'runnable'"
                type="button"
                class="ghost"
                :disabled="!!busy"
                @click="emit('run', j.job_id, false)"
              >
                异步执行
              </button>
              <span v-else class="muted tip" :title="j.run_hint || ''">{{
                j.status_label || KIND_TITLE[j.job_kind]
              }}</span>
            </td>
          </tr>
        </template>
      </tbody>
    </table>
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
.actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  align-items: center;
}
.filter {
  border-radius: 0.5rem;
  padding: 0.4rem 0.75rem;
  border: 1px solid var(--line);
  background: var(--surface);
  color: var(--ink);
  font-size: 0.8125rem;
}
tr.section td {
  border-bottom: 1px solid var(--border);
  padding-top: 12px;
  color: var(--muted);
  font-size: 0.82rem;
}
tr.section strong {
  color: var(--text);
  margin-right: 2px;
}
.toggle:disabled {
  opacity: 0.45;
  cursor: not-allowed;
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
.primary,
.ghost,
.toggle {
  border-radius: 0.5rem;
  padding: 8px 12px;
  border: 1px solid var(--border);
  cursor: pointer;
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
.toggle {
  background: var(--bg);
  color: var(--muted);
  min-width: 44px;
}
.toggle.on {
  background: #ecfdf5;
  color: #166534;
  border-color: #86efac;
}
.tip {
  cursor: help;
}
</style>

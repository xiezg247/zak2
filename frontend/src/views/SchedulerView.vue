<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import AppShell from '../components/AppShell.vue'
import { fmtDateTime } from '../lib/format'
import { opsApi, type OpsJob, type SchedulerJob } from '../api/ops'
import { filterJobs, groupJobs, KIND_TITLE, type JobFilter } from './opsJobGroups'

const jobs = ref<SchedulerJob[]>([])
const jobFilter = ref<JobFilter>('all')
const jobGroups = computed(() => groupJobs(filterJobs(jobs.value, jobFilter.value)))
const error = ref('')
const busy = ref('')
const message = ref('')

const recentJobs = ref<OpsJob[]>([])
let pollTimer: number | undefined

const STATUS_LABEL: Record<string, string> = {
  pending: '排队中',
  running: '运行中',
  success: '成功',
  failed: '失败',
}

function statusLabel(status: string): string {
  return STATUS_LABEL[status] || status
}

function jobNameFor(kind: string): string {
  const jobId = kind.startsWith('ops.') ? kind.slice(4) : kind
  return jobs.value.find((j) => j.job_id === jobId)?.name || kind
}

async function loadRecentJobs() {
  try {
    recentJobs.value = await opsApi.jobsRecent()
  } catch {
    /* 轮询失败静默，避免反复报错 */
  }
}

function startPolling() {
  stopPolling()
  void loadRecentJobs()
  pollTimer = window.setInterval(() => {
    void loadRecentJobs()
  }, 3000)
}

function stopPolling() {
  if (pollTimer != null) window.clearInterval(pollTimer)
  pollTimer = undefined
}

async function refresh() {
  error.value = ''
  try {
    jobs.value = await opsApi.jobs()
  } catch (e) {
    error.value = e instanceof Error ? e.message : '加载失败'
  }
}

async function toggle(job: SchedulerJob) {
  if (job.job_kind !== 'runnable' && !job.enabled) return
  const nextEnabled = job.job_kind === 'runnable' ? !job.enabled : false
  busy.value = job.job_id
  try {
    const updated = await opsApi.setEnabled(job.job_id, nextEnabled)
    jobs.value = jobs.value.map((row) => (row.job_id === updated.job_id ? updated : row))
  } catch (e) {
    error.value = e instanceof Error ? e.message : '更新失败'
  } finally {
    busy.value = ''
  }
}

async function runJob(jobId: string, sync = false) {
  busy.value = jobId
  message.value = ''
  try {
    if (sync) {
      if (jobId === 'purge_stale_cache') {
        message.value = (await opsApi.purge()).message
      } else if (jobId === 'sync_trade_calendar') {
        message.value = (await opsApi.syncCalendar()).message
      } else if (jobId === 'sync_sector_flow_daily') {
        message.value = (await opsApi.syncSectorFlow()).message
      } else if (jobId === 'screen_intraday') {
        message.value = (await opsApi.screenIntraday()).message
      } else if (jobId === 'screen_post_close') {
        message.value = (await opsApi.screenPostClose()).message
      } else if (
        jobId === 'sync_universe' ||
        jobId === 'sync_stock_industry' ||
        jobId === 'fill_watchlist_bars' ||
        jobId === 'batch_fill_stale' ||
        jobId === 'batch_download_universe' ||
        jobId === 'warm_market_summary' ||
        jobId === 'sync_bilibili_feed'
      ) {
        const accepted = await opsApi.runJob(jobId)
        message.value = `已提交 ${accepted.kind}（${accepted.job_id}）`
      } else {
        throw new Error('不支持同步执行')
      }
    } else {
      const accepted = await opsApi.runJob(jobId)
      message.value = `已提交异步任务 ${accepted.job_id}（${accepted.kind}）`
    }
    await refresh()
    await loadRecentJobs()
  } catch (e) {
    error.value = e instanceof Error ? e.message : '执行失败'
  } finally {
    busy.value = ''
  }
}

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

onMounted(() => {
  void refresh()
  startPolling()
})

onUnmounted(() => {
  stopPolling()
})
</script>

<template>
  <AppShell
    title="调度"
    subtitle="内嵌调度覆盖全部可跑 job · 盘中/盘后选股需配置 SCHEDULER_SCREEN_USER_ID"
    active="scheduler"
  >
    <div class="page">
      <p v-if="error" class="err">{{ error }}</p>
      <p v-if="message" class="ok">{{ message }}</p>

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
            <button type="button" class="ghost" :disabled="!!busy" @click="refresh">刷新</button>
            <button
              type="button"
              class="ghost"
              :disabled="!!busy"
              @click="runJob('sync_trade_calendar', true)"
            >
              同步日历
            </button>
            <button
              type="button"
              class="ghost"
              :disabled="!!busy"
              @click="runJob('sync_sector_flow_daily', true)"
            >
              同步板块资金
            </button>
            <button
              type="button"
              class="ghost"
              :disabled="!!busy"
              @click="runJob('screen_intraday', true)"
            >
              盘中选股
            </button>
            <button
              type="button"
              class="ghost"
              :disabled="!!busy"
              @click="runJob('screen_post_close', true)"
            >
              盘后选股
            </button>
            <button
              type="button"
              class="ghost"
              :disabled="!!busy"
              @click="runJob('warm_market_summary', true)"
            >
              {{ busy === 'warm_market_summary' ? '提交中…' : '预热情绪周期' }}
            </button>
            <button
              type="button"
              class="ghost"
              :disabled="!!busy"
              @click="runJob('sync_bilibili_feed', true)"
            >
              {{ busy === 'sync_bilibili_feed' ? '提交中…' : 'B站订阅同步' }}
            </button>
            <button
              type="button"
              class="primary"
              :disabled="!!busy"
              @click="runJob('purge_stale_cache', true)"
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
                    @click="toggle(j)"
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
                    @click="runJob(j.job_id, false)"
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

      <section class="panel">
        <div class="toolbar">
          <div>
            <h2>日 K 数据同步</h2>
            <p class="muted">
              同步 A 股列表 / 行业映射，补全自选与过期日 K；全市场首下需 TUSHARE_TOKEN、app.universe
              与 BARS_UNIVERSE_START。
            </p>
          </div>
        </div>
        <div class="actions" style="margin-top: 8px">
          <button
            type="button"
            class="ghost"
            :disabled="!!busy"
            @click="runJob('sync_universe', true)"
          >
            {{ busy === 'sync_universe' ? '提交中…' : '同步 A 股列表' }}
          </button>
          <button
            type="button"
            class="ghost"
            :disabled="!!busy"
            @click="runJob('sync_stock_industry', true)"
          >
            {{ busy === 'sync_stock_industry' ? '提交中…' : '同步行业映射' }}
          </button>
          <button
            type="button"
            class="ghost"
            :disabled="!!busy"
            @click="runJob('fill_watchlist_bars', true)"
          >
            {{ busy === 'fill_watchlist_bars' ? '提交中…' : '补全自选日 K' }}
          </button>
          <button
            type="button"
            class="ghost"
            :disabled="!!busy"
            @click="runJob('batch_fill_stale', true)"
          >
            {{ busy === 'batch_fill_stale' ? '提交中…' : '补全过期日 K' }}
          </button>
          <button
            type="button"
            class="ghost"
            :disabled="!!busy"
            @click="runJob('batch_download_universe', true)"
          >
            {{ busy === 'batch_download_universe' ? '提交中…' : '全市场日 K 首下' }}
          </button>
        </div>
      </section>

      <section class="panel">
        <div class="toolbar">
          <div>
            <h2>任务进度</h2>
            <p class="muted">异步执行的 job 状态与进度，每 3 秒自动刷新</p>
          </div>
          <button type="button" class="ghost" @click="loadRecentJobs">刷新</button>
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
.ok {
  color: var(--ok);
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

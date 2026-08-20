<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import AppShell from '../../../components/AppShell.vue'
import { opsApi, type OpsJob, type SchedulerJob } from '../../../api/ops'
import { filterJobs, groupJobs, type JobFilter } from '../opsJobGroups'
import SchedulerJobsPanel from '../components/SchedulerJobsPanel.vue'
import SchedulerProgressPanel from '../components/SchedulerProgressPanel.vue'

const jobs = ref<SchedulerJob[]>([])
const jobFilter = ref<JobFilter>('all')
const jobGroups = computed(() => groupJobs(filterJobs(jobs.value, jobFilter.value)))
const error = ref('')
const busy = ref('')
const message = ref('')

const recentJobs = ref<OpsJob[]>([])
let pollTimer: number | undefined

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

      <SchedulerJobsPanel
        v-model:job-filter="jobFilter"
        :job-groups="jobGroups"
        :busy="busy"
        @refresh="refresh"
        @toggle="toggle"
        @run="runJob"
      />

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

      <SchedulerProgressPanel
        :recent-jobs="recentJobs"
        :job-name-for="jobNameFor"
        @refresh="loadRecentJobs"
      />
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
.muted {
  color: var(--muted);
  font-size: 0.78rem;
}
.err {
  color: var(--danger);
  margin: 0;
}
.ok {
  color: var(--ok);
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
</style>

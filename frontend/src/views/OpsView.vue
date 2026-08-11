<script setup lang="ts">
import { onMounted, ref } from 'vue'
import AppShell from '../components/AppShell.vue'
import { opsApi, type BarsOverview, type Health, type SchedulerJob } from '../api/ops'

const health = ref<Health | null>(null)
const bars = ref<BarsOverview | null>(null)
const jobs = ref<SchedulerJob[]>([])
const error = ref('')
const busy = ref('')
const message = ref('')

async function refresh() {
  error.value = ''
  const [h, b, j] = await Promise.all([opsApi.health(), opsApi.barsOverview(), opsApi.jobs()])
  health.value = h
  bars.value = b
  jobs.value = j
}

async function toggle(job: SchedulerJob) {
  busy.value = job.job_id
  try {
    const updated = await opsApi.setEnabled(job.job_id, !job.enabled)
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
  } catch (e) {
    error.value = e instanceof Error ? e.message : '执行失败'
  } finally {
    busy.value = ''
  }
}

async function forceCollector() {
  busy.value = 'collector_force'
  message.value = ''
  try {
    const result = await opsApi.forceCollector()
    message.value = result.message
    if (!result.success) {
      error.value = result.message
    }
    await refresh()
  } catch (e) {
    error.value = e instanceof Error ? e.message : '强制采集失败'
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

onMounted(async () => {
  try {
    await refresh()
  } catch (e) {
    error.value = e instanceof Error ? e.message : '加载失败'
  }
})
</script>

<template>
  <AppShell title="运维" subtitle="健康 · 日 K · 内嵌调度 · 可跑 sync" active="ops">
    <div class="page">
      <p v-if="error" class="err">{{ error }}</p>
      <p v-if="message" class="ok">{{ message }}</p>

      <section v-if="health" class="cards">
        <div class="card" :class="{ bad: !health.postgres.ok }">
          <h3>PostgreSQL</h3>
          <p>{{ health.postgres.ok ? '正常' : '异常' }}</p>
          <p class="muted">{{ health.postgres.url }}</p>
        </div>
        <div class="card" :class="{ bad: !health.redis.ok }">
          <h3>Redis 行情</h3>
          <p>{{ health.redis.ok ? '正常' : '不可用' }}</p>
          <p class="muted">quotes {{ health.redis.quote_count ?? 0 }} · {{ health.redis.updated_at || '无更新时间' }}</p>
        </div>
        <div class="card" :class="{ bad: !health.quote_collector?.running }">
          <h3>行情采集</h3>
          <p>{{ health.quote_collector?.running ? '运行中' : '未运行' }}</p>
          <p class="muted">
            {{
              health.quote_collector?.running
                ? `${health.quote_collector?.provider || '—'} · ${health.quote_collector?.status || '—'} · 最近 ${health.quote_collector?.last_count ?? 0} 条`
                : health.quote_collector?.hint || 'python -m app.quote_collector'
            }}
          </p>
          <div class="actions" style="margin-top: 8px">
            <button type="button" class="ghost" :disabled="!!busy" @click="forceCollector">
              {{ busy === 'collector_force' ? '发送中…' : '强制采一轮' }}
            </button>
          </div>
        </div>
        <div class="card" :class="{ bad: !health.llm.configured }">
          <h3>LLM</h3>
          <p>{{ health.llm.configured ? health.llm.model : '未配置 KEY' }}</p>
          <p class="muted">{{ health.llm.api_base }}</p>
        </div>
        <div class="card" :class="{ bad: !health.tushare_configured }">
          <h3>Tushare</h3>
          <p>{{ health.tushare_configured ? '已配置' : '未配置' }}</p>
          <p class="muted">日历 / 板块 / 日 K / 封板时间</p>
        </div>
        <div class="card" :class="{ bad: Boolean(health.mcp?.enabled) && health.mcp?.status !== '已连接' }">
          <h3>MCP</h3>
          <p>{{ health.mcp?.status || '未启用' }}</p>
          <p class="muted">
            {{
              health.mcp?.tool_count != null
                ? `白名单工具 ${health.mcp.tool_count} · Streamable HTTP`
                : 'Streamable HTTP · 诊断只读'
            }}
          </p>
        </div>
        <div class="card" :class="{ bad: health.scheduler_lock?.ok === false || !health.redis.ok }">
          <h3>调度锁</h3>
          <p>
            {{
              health.scheduler_lock?.ok === false || !health.redis.ok
                ? '不可用'
                : `Redis 锁 · TTL ${health.scheduler_lock?.ttl_seconds ?? '—'}s`
            }}
          </p>
          <p class="muted">{{ health.scheduler_lock?.key_prefix || 'zak2:scheduler:lock:' }}</p>
        </div>
      </section>

      <section v-if="bars" class="panel bars">
        <div class="toolbar">
          <h2>本地日 K Overview</h2>
          <span class="muted">as of {{ bars.as_of_trade_date || '—' }} · interval={{ bars.interval }}</span>
        </div>
        <div class="stat-row">
          <div><strong>{{ bars.symbol_count }}</strong><span class="muted">标的</span></div>
          <div><strong>{{ bars.ok_count }}</strong><span class="muted">最新</span></div>
          <div class="warn"><strong>{{ bars.stale_count }}</strong><span class="muted">过期</span></div>
          <div><strong>{{ bars.unknown_count }}</strong><span class="muted">未知</span></div>
        </div>
        <p class="muted">
          区间 {{ bars.min_start || '—' }} → {{ bars.max_end || '—' }}
          · Web 可同步 A 股列表 / 行业映射 → app.stock_industry / 补全自选 / 过期 / 全市场首下（需 TUSHARE_TOKEN；首下另需 app.universe；起点 BARS_UNIVERSE_START）
        </p>
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
            <h2>定时任务</h2>
            <p class="muted">
              内嵌调度覆盖全部可跑 job；盘中/盘后选股定时需配置环境变量 SCHEDULER_SCREEN_USER_ID
              · 预热情绪周期写入短 TTL 缓存 · B 站同步需 BILIBILI_COOKIES
            </p>
          </div>
          <div class="actions">
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
            <button type="button" class="primary" :disabled="!!busy" @click="runJob('purge_stale_cache', true)">
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
            <tr v-for="j in jobs" :key="j.job_id">
              <td>
                <div class="name">{{ j.name }}</div>
                <div class="muted">{{ j.job_id }} · {{ j.description }}</div>
              </td>
              <td>
                <button
                  type="button"
                  class="toggle"
                  :class="{ on: j.enabled }"
                  :disabled="busy === j.job_id"
                  @click="toggle(j)"
                >
                  {{ j.enabled ? '开' : '关' }}
                </button>
              </td>
              <td class="mono">{{ scheduleText(j) }}</td>
              <td>
                <template v-if="j.last_run">
                  <div :class="j.last_run.last_success === false ? 'err' : ''">
                    {{ j.last_run.last_success === false ? '失败' : j.last_run.last_success ? '成功' : '—' }}
                    · {{ j.last_run.last_run_at }}
                  </div>
                  <div class="muted">{{ j.last_run.last_message }}</div>
                </template>
                <span v-else class="muted">无记录</span>
              </td>
              <td>
                <button
                  v-if="j.runnable"
                  type="button"
                  class="ghost"
                  :disabled="!!busy"
                  @click="runJob(j.job_id, false)"
                >
                  异步执行
                </button>
                <span v-else class="muted tip" :title="j.run_hint || ''">{{ j.status_label || '未实现' }}</span>
              </td>
            </tr>
          </tbody>
        </table>
      </section>
    </div>
  </AppShell>
</template>

<style scoped>
.page {
  padding: 16px 20px;
  display: grid;
  gap: 16px;
}
.cards {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
}
.card,
.panel {
  border: 1px solid var(--border);
  border-radius: 10px;
  background: var(--bg-elevated);
  padding: 12px 14px;
}
.card.bad {
  border-color: #7a3a3a;
}
.card h3 {
  margin: 0 0 6px;
  font-size: 0.85rem;
  color: var(--muted);
  font-weight: 600;
}
.card p {
  margin: 0 0 4px;
}
.panel {
  overflow: auto;
}
.bars .stat-row {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
  margin: 8px 0;
}
.stat-row div {
  display: grid;
  gap: 2px;
}
.stat-row strong {
  font-size: 1.25rem;
}
.stat-row .warn strong {
  color: #d4a15c;
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
  color: #6fbf8a;
  margin: 0;
}
.primary,
.ghost,
.toggle {
  border-radius: 8px;
  padding: 8px 12px;
  border: 1px solid var(--border);
  cursor: pointer;
}
.primary {
  background: var(--accent);
  border-color: transparent;
  color: #fff;
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
  background: #24553a;
  color: #d8ffe8;
  border-color: #2f6b48;
}
.tip {
  cursor: help;
}
@media (max-width: 1100px) {
  .cards,
  .bars .stat-row {
    grid-template-columns: 1fr 1fr;
  }
}
@media (max-width: 700px) {
  .cards,
  .bars .stat-row {
    grid-template-columns: 1fr;
  }
}
</style>

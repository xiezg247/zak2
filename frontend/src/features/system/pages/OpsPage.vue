<script setup lang="ts">
import { onMounted, ref } from 'vue'
import AppShell from '../../../components/AppShell.vue'
import { fmtDateTime } from '../../../lib/format'
import { opsApi, type BarsOverview, type Health } from '../../../api/ops'

const health = ref<Health | null>(null)
const bars = ref<BarsOverview | null>(null)
const error = ref('')
const busy = ref('')
const message = ref('')

async function refresh() {
  error.value = ''
  const [h, b] = await Promise.all([opsApi.health(), opsApi.barsOverview()])
  health.value = h
  bars.value = b
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

onMounted(async () => {
  try {
    await refresh()
  } catch (e) {
    error.value = e instanceof Error ? e.message : '加载失败'
  }
})
</script>

<template>
  <AppShell title="运维" subtitle="健康 · 日 K" active="ops">
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
          <p class="muted">
            quotes {{ health.redis.quote_count ?? 0 }} ·
            {{ fmtDateTime(health.redis.updated_at) || '无更新时间' }}
          </p>
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
        <div
          class="card"
          :class="{ bad: Boolean(health.mcp?.enabled) && health.mcp?.status !== '已连接' }"
        >
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
          <span class="muted"
            >as of {{ bars.as_of_trade_date || '—' }} · interval={{ bars.interval }}</span
          >
        </div>
        <div class="stat-row">
          <div>
            <strong>{{ bars.symbol_count }}</strong
            ><span class="muted">标的</span>
          </div>
          <div>
            <strong>{{ bars.ok_count }}</strong
            ><span class="muted">最新</span>
          </div>
          <div class="warn">
            <strong>{{ bars.stale_count }}</strong
            ><span class="muted">过期</span>
          </div>
          <div>
            <strong>{{ bars.unknown_count }}</strong
            ><span class="muted">未知</span>
          </div>
        </div>
        <p class="muted">
          区间 {{ bars.min_start || '—' }} → {{ bars.max_end || '—' }}
          · 数据同步在「调度」页执行（A 股列表 / 行业映射 / 补全自选 / 过期 / 全市场首下）
        </p>
      </section>
    </div>
  </AppShell>
</template>

<style scoped>
.page {
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
  border: 1px solid var(--line);
  border-radius: 0.75rem;
  background: var(--surface);
  box-shadow: var(--shadow-card);
  padding: 14px 16px;
}
.card.bad {
  border-color: var(--danger);
  background: #fff5f5;
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
  color: var(--brand-dark);
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
.ghost {
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

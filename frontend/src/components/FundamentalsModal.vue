<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { fmtDateTime } from '../lib/format'
import { watchlistApi, type Fundamentals } from '../api/watchlist'

const vt = defineModel<string>('vt', { default: '' })

const props = defineProps<{
  name?: string
}>()

const fund = ref<Fundamentals | null>(null)
const error = ref('')
const loading = ref(false)

const title = computed(() => props.name?.trim() || vt.value)

function formatYmd(raw: string | null | undefined): string {
  const s = (raw || '').trim()
  if (!s) return '—'
  if (/^\d{8}$/.test(s)) return `${s.slice(0, 4)}-${s.slice(4, 6)}-${s.slice(6, 8)}`
  return s
}

function formatMoney(n: number | null | undefined): string {
  if (n == null || Number.isNaN(n)) return '—'
  if (Math.abs(n) >= 1e8) return `${(n / 1e8).toFixed(2)} 亿`
  if (Math.abs(n) >= 1e4) return `${(n / 1e4).toFixed(2)} 万`
  return n.toFixed(2)
}

function formatRatioPct(n: number | null | undefined): string {
  if (n == null || Number.isNaN(n)) return '—'
  return `${(n * 100).toFixed(1)}%`
}

async function load() {
  const symbol = vt.value
  error.value = ''
  fund.value = null
  if (!symbol) {
    loading.value = false
    return
  }
  loading.value = true
  try {
    fund.value = await watchlistApi.fundamentals(symbol)
  } catch (e) {
    error.value = e instanceof Error ? e.message : '基本面加载失败'
  } finally {
    loading.value = false
  }
}

function close() {
  vt.value = ''
  fund.value = null
  error.value = ''
  loading.value = false
}

watch(vt, (v) => {
  if (v) void load()
  else {
    fund.value = null
    error.value = ''
    loading.value = false
  }
})

function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape' && vt.value) close()
}

onMounted(() => document.addEventListener('keydown', onKeydown))
onUnmounted(() => document.removeEventListener('keydown', onKeydown))
</script>

<template>
  <Teleport to="body">
    <div v-if="vt" class="chart-overlay" @click.self="close">
      <div class="chart-modal fund-modal" role="dialog" aria-modal="true" aria-label="基本面">
        <div class="chart-modal-head">
          <strong>{{ title }}</strong>
          <span class="mono muted">{{ vt }}</span>
          <div class="spacer"></div>
          <button type="button" class="icon-btn" title="关闭" @click="close">
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
              stroke-linecap="round"
              stroke-linejoin="round"
            >
              <path d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
        <p v-if="loading" class="muted">加载基本面…</p>
        <p v-else-if="error" class="err">{{ error }}</p>
        <template v-else-if="fund">
          <div class="fund-block">
            <h4>财报</h4>
            <template v-if="fund.snapshot">
              <p class="muted">
                期末 {{ formatYmd(fund.snapshot.end_date) }}
                <span v-if="fund.sync?.last_sync_at">
                  · 同步 {{ fmtDateTime(fund.sync.last_sync_at) }}</span
                >
              </p>
              <dl class="fund-grid">
                <div>
                  <dt>营收</dt>
                  <dd class="mono">{{ formatMoney(fund.snapshot.revenue) }}</dd>
                </div>
                <div>
                  <dt>净利</dt>
                  <dd class="mono">{{ formatMoney(fund.snapshot.net_income) }}</dd>
                </div>
                <div>
                  <dt>营收同比</dt>
                  <dd>{{ formatRatioPct(fund.snapshot.revenue_yoy) }}</dd>
                </div>
                <div>
                  <dt>净利同比</dt>
                  <dd>{{ formatRatioPct(fund.snapshot.net_income_yoy) }}</dd>
                </div>
                <div>
                  <dt>ROE</dt>
                  <dd>{{ formatRatioPct(fund.snapshot.roe) }}</dd>
                </div>
                <div>
                  <dt>资产负债率</dt>
                  <dd>{{ formatRatioPct(fund.snapshot.debt_ratio) }}</dd>
                </div>
              </dl>
            </template>
            <p v-else class="muted">
              暂无财报
              <RouterLink to="/ops" class="draft-link">去 Ops 同步自选财报</RouterLink>
            </p>
          </div>
          <div class="fund-block">
            <h4>披露</h4>
            <template v-if="fund.disclosures.length">
              <table class="fund-disc">
                <thead>
                  <tr>
                    <th>报告期</th>
                    <th>预告</th>
                    <th>公告</th>
                    <th>实际</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="d in fund.disclosures" :key="d.end_date">
                    <td class="mono">{{ formatYmd(d.end_date) }}</td>
                    <td class="mono">{{ formatYmd(d.pre_date) }}</td>
                    <td class="mono">{{ formatYmd(d.ann_date) }}</td>
                    <td class="mono">{{ formatYmd(d.actual_date) }}</td>
                  </tr>
                </tbody>
              </table>
            </template>
            <p v-else class="muted">
              暂无披露日历
              <RouterLink to="/ops" class="draft-link">去 Ops 同步披露计划</RouterLink>
            </p>
          </div>
        </template>
        <p v-else class="muted">无基本面数据</p>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.chart-overlay {
  position: fixed;
  inset: 0;
  z-index: 1000;
  display: grid;
  place-items: center;
  background: rgba(0, 0, 0, 0.45);
  padding: 24px;
}
.chart-modal {
  width: 100%;
  max-width: 860px;
  max-height: 88vh;
  overflow: auto;
  display: grid;
  gap: 12px;
  padding: 16px 18px;
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: 0.875rem;
  box-shadow: var(--shadow-panel);
}
.fund-modal {
  max-width: 560px;
}
.chart-modal-head {
  display: flex;
  align-items: baseline;
  gap: 8px;
}
.chart-modal-head strong {
  font-size: 1rem;
}
.chart-modal-head .mono {
  font-size: 0.78rem;
}
.chart-modal-head .spacer {
  flex: 1;
}
.fund-block {
  display: grid;
  gap: 6px;
}
.fund-block h4 {
  margin: 0;
  font-size: 0.85rem;
}
.fund-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px 12px;
  margin: 0;
}
.fund-grid dt {
  font-size: 0.75rem;
  color: var(--muted);
}
.fund-grid dd {
  margin: 2px 0 0;
  font-size: 0.875rem;
}
.fund-disc {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.8rem;
}
.fund-disc th,
.fund-disc td {
  padding: 5px 8px;
  border-bottom: 1px solid var(--line-soft);
  text-align: left;
}
.fund-disc th {
  color: var(--muted);
  font-weight: 500;
  background: var(--surface-muted);
}
.icon-btn {
  display: inline-grid;
  place-items: center;
  width: 26px;
  height: 24px;
  padding: 0;
  border: 1px solid var(--line);
  border-radius: 0.4rem;
  background: transparent;
  color: var(--ink-muted);
  cursor: pointer;
}
.icon-btn:hover {
  background: var(--surface-muted);
  border-color: var(--brand);
  color: var(--brand);
}
.icon-btn svg {
  width: 15px;
  height: 15px;
}
.err {
  margin: 0;
  color: var(--danger);
  font-size: 0.85rem;
}
.muted {
  color: var(--muted);
  font-size: 0.85rem;
}
.mono {
  font-family: var(--mono);
}
.draft-link {
  color: var(--brand);
  margin-left: 4px;
}
</style>

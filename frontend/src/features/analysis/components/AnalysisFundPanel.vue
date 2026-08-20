<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { useStockAnalysis } from '../composables/useStockAnalysis'
import { watchlistApi, type Fundamentals } from '../../../api/watchlist'
import { fmtDateTime } from '../../../lib/format'

const analysis = useStockAnalysis()

const fund = ref<Fundamentals | null>(null)
const fundErr = ref('')
const fundLoading = ref(false)

async function loadFund() {
  if (!analysis.vtSymbol.value || analysis.isLoaded('fundamental')) return
  fundLoading.value = true
  fundErr.value = ''
  try {
    fund.value = await watchlistApi.fundamentals(analysis.vtSymbol.value)
    analysis.markLoaded('fundamental')
  } catch (e) {
    fundErr.value = e instanceof Error ? e.message : '基本面加载失败'
  } finally {
    fundLoading.value = false
  }
}

function fmtYmd(raw: string | null | undefined): string {
  const s = (raw || '').trim()
  if (!s) return '—'
  if (/^\d{8}$/.test(s)) return `${s.slice(0, 4)}-${s.slice(4, 6)}-${s.slice(6, 8)}`
  return s.slice(0, 10)
}

function fmtMoney(n: number | null | undefined): string {
  if (n == null || Number.isNaN(n)) return '—'
  if (Math.abs(n) >= 1e8) return `${(n / 1e8).toFixed(2)} 亿`
  if (Math.abs(n) >= 1e4) return `${(n / 1e4).toFixed(2)} 万`
  return n.toFixed(2)
}

function fmtRatioPct(n: number | null | undefined): string {
  if (n == null || Number.isNaN(n)) return '—'
  return `${(n * 100).toFixed(1)}%`
}

function maybeLoad() {
  if (
    analysis.activeTab.value === 'fundamental' &&
    analysis.vtSymbol.value &&
    !analysis.isLoaded('fundamental')
  ) {
    void loadFund()
  }
}

onMounted(() => maybeLoad())

watch(() => analysis.activeTab.value, () => maybeLoad())

watch(
  () => analysis.vtSymbol.value,
  () => {
    fund.value = null
    maybeLoad()
  },
)
</script>

<template>
  <div class="fund-tab">
    <p v-if="fundLoading" class="hint">加载基本面…</p>
    <p v-else-if="fundErr" class="err">{{ fundErr }}</p>
    <template v-else-if="fund">
      <section class="fund-block">
        <div class="block-head">
          <h4>财报</h4>
          <span v-if="fund.sync?.last_sync_at" class="block-sub mono">{{
            fmtYmd(fund.sync.last_sync_at)
          }}</span>
        </div>
        <template v-if="fund.snapshot">
          <p class="muted block-meta">
            期末 {{ fmtYmd(fund.snapshot.end_date)
            }}<span v-if="fund.sync?.last_sync_at">
              · 同步 {{ fmtDateTime(fund.sync.last_sync_at) }}</span
            >
          </p>
          <dl class="fund-grid">
            <div>
              <dt>营收</dt>
              <dd class="mono">{{ fmtMoney(fund.snapshot.revenue) }}</dd>
            </div>
            <div>
              <dt>净利</dt>
              <dd class="mono">{{ fmtMoney(fund.snapshot.net_income) }}</dd>
            </div>
            <div>
              <dt>营收同比</dt>
              <dd>{{ fmtRatioPct(fund.snapshot.revenue_yoy) }}</dd>
            </div>
            <div>
              <dt>净利同比</dt>
              <dd>{{ fmtRatioPct(fund.snapshot.net_income_yoy) }}</dd>
            </div>
            <div>
              <dt>ROE</dt>
              <dd>{{ fmtRatioPct(fund.snapshot.roe) }}</dd>
            </div>
            <div>
              <dt>资产负债率</dt>
              <dd>{{ fmtRatioPct(fund.snapshot.debt_ratio) }}</dd>
            </div>
          </dl>
        </template>
        <p v-else class="hint">暂无财报，可点右上角同步按钮拉取。</p>
      </section>
      <section class="fund-block">
        <div class="block-head">
          <h4>披露</h4>
          <span class="block-sub">报告期 · 预告 · 公告 · 实际</span>
        </div>
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
                <td class="mono">{{ fmtYmd(d.end_date) }}</td>
                <td class="mono">{{ fmtYmd(d.pre_date) }}</td>
                <td class="mono">{{ fmtYmd(d.ann_date) }}</td>
                <td class="mono">{{ fmtYmd(d.actual_date) }}</td>
              </tr>
            </tbody>
          </table>
        </template>
        <p v-else class="hint">暂无披露日历。</p>
      </section>
    </template>
    <p v-else class="hint">无基本面数据</p>
  </div>
</template>

<style scoped>
.mono {
  font-family: var(--mono);
}
.muted {
  color: var(--muted);
}
.err {
  margin: 0;
  color: var(--danger);
  font-size: 0.85rem;
}
.hint {
  margin: 4px 0;
  padding: 18px 12px;
  border: 1px dashed var(--line);
  border-radius: 0.6rem;
  background: var(--surface-muted);
  color: var(--muted);
  font-size: 0.82rem;
  text-align: center;
}
.block-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
.block-head h4 {
  margin: 0;
  font-size: 0.88rem;
  font-weight: 600;
  color: var(--ink);
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.block-head h4::before {
  content: '';
  width: 3px;
  height: 12px;
  border-radius: 2px;
  background: var(--brand);
}
.block-sub {
  color: var(--muted);
  font-size: 0.72rem;
}
.block-meta {
  margin: 0;
  font-size: 0.75rem;
}
.fund-tab {
  display: grid;
  gap: 12px;
}
.fund-block {
  display: grid;
  gap: 10px;
  border: 1px solid var(--line);
  border-radius: 0.75rem;
  background: var(--surface);
  padding: 14px 16px;
  box-shadow: var(--shadow-card);
}
.fund-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 1px;
  margin: 0;
  border: 1px solid var(--line);
  border-radius: 0.6rem;
  overflow: hidden;
  background: var(--line);
}
.fund-grid > div {
  display: grid;
  gap: 3px;
  padding: 10px 12px;
  background: var(--surface-muted);
}
.fund-grid dt {
  color: var(--muted);
  font-size: 0.72rem;
}
.fund-grid dd {
  margin: 0;
  font-size: 0.88rem;
  font-weight: 600;
  color: var(--ink);
  font-variant-numeric: tabular-nums;
}
.fund-disc {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.8rem;
}
.fund-disc th,
.fund-disc td {
  padding: 7px 10px;
  border-bottom: 1px solid var(--line-soft);
  text-align: left;
}
.fund-disc tr:last-child td {
  border-bottom: none;
}
.fund-disc th {
  color: var(--muted);
  font-weight: 500;
  background: var(--surface-muted);
}

@media (max-width: 560px) {
  .fund-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>

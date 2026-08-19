<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useStockAnalysis, type AnalysisTabKey } from '../composables/useStockAnalysis'
import CandleChart from './CandleChart.vue'
import {
  watchlistApi,
  type QuoteOut,
  type Fundamentals,
  type StrategySignalRow,
} from '../api/watchlist'
import { marketApi } from '../api/market'
import { aiApi } from '../api/ai'
import { opsApi } from '../api/ops'
import {
  contentApi,
  type TeamReportListItem,
  type TeamReport,
  type NoteMemo,
  type NoteEntry,
} from '../api/content'
import MarkdownView from './MarkdownView.vue'
import type { BoardSignalMode } from '../lib/boardBacktestParams'

const analysis = useStockAnalysis()

const TABS: { key: AnalysisTabKey; label: string }[] = [
  { key: 'quote', label: '行情' },
  { key: 'fundamental', label: '基本面' },
  { key: 'signal', label: '策略信号' },
  { key: 'radar', label: '雷达' },
  { key: 'ai', label: 'AI研报' },
  { key: 'notes', label: '笔记' },
]

const displayName = computed(() => analysis.name.value || analysis.vtSymbol.value || '—')

function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape' && analysis.isOpen.value) analysis.close()
}

function switchTab(tab: AnalysisTabKey) {
  analysis.activeTab.value = tab
}

const quote = ref<QuoteOut | null>(null)
const quoteErr = ref('')
const quoteLoading = ref(false)
const barInterval = ref<'d' | '1m'>('d')
const barLimit = ref(90)
const bars = ref<
  { datetime: string; open: number; high: number; low: number; close: number; volume: number }[]
>([])
const barsErr = ref('')
const barsLoading = ref(false)

const barLimitChoices = computed(() =>
  barInterval.value === '1m' ? [240, 480, 1200] : [60, 90, 120],
)

async function loadQuote() {
  if (!analysis.vtSymbol.value || analysis.isLoaded('quote')) return
  quoteLoading.value = true
  quoteErr.value = ''
  try {
    const quotes = await watchlistApi.quotes(analysis.vtSymbol.value)
    quote.value = quotes.find((q) => q.vt_symbol === analysis.vtSymbol.value) || null
    analysis.markLoaded('quote')
  } catch (e) {
    quoteErr.value = e instanceof Error ? e.message : '行情加载失败'
  } finally {
    quoteLoading.value = false
  }
}

async function loadBars() {
  if (!analysis.vtSymbol.value) return
  barsLoading.value = true
  barsErr.value = ''
  try {
    const resp = await watchlistApi.bars(analysis.vtSymbol.value, barInterval.value, barLimit.value)
    bars.value = resp.bars
  } catch (e) {
    barsErr.value = e instanceof Error ? e.message : '无 K 线'
  } finally {
    barsLoading.value = false
  }
}

watch(
  () => analysis.activeTab.value,
  (tab) => {
    if (tab === 'quote' && analysis.vtSymbol.value && !analysis.isLoaded('quote')) void loadQuote()
    if (tab === 'fundamental' && analysis.vtSymbol.value && !analysis.isLoaded('fundamental'))
      void loadFund()
    if (tab === 'signal' && analysis.vtSymbol.value && !analysis.isLoaded('signal'))
      void loadSignals()
    if (tab === 'radar' && analysis.vtSymbol.value && !analysis.isLoaded('radar')) void loadRadar()
    if (tab === 'ai' && analysis.vtSymbol.value && !analysis.isLoaded('ai')) {
      analysis.markLoaded('ai')
      void checkAiStatus()
      void loadReportList()
    }
    if (tab === 'notes' && analysis.vtSymbol.value && !notesLoaded.value) void loadNotes()
  },
)

watch(
  () => analysis.vtSymbol.value,
  (vt) => {
    if (vt) void loadQuote()
    syncMsg.value = ''
    syncErr.value = ''
    syncMenuOpen.value = false
    syncBusy.value = ''
  },
)

function switchInterval(iv: 'd' | '1m') {
  if (barInterval.value === iv) return
  barInterval.value = iv
  barLimit.value = iv === '1m' ? 480 : 90
  void loadBars()
}

function switchBarLimit(n: number) {
  barLimit.value = n
  void loadBars()
}

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

const SIGNAL_MODES: { id: BoardSignalMode; label: string }[] = [
  { id: 'heuristic_v2', label: '启发式确认' },
  { id: 'double_ma', label: '回测双均线' },
  { id: 'trend_ma', label: '趋势均线' },
  { id: 'medium_swing', label: '中线波段' },
]
const signalRows = ref<{ mode: string; row: StrategySignalRow }[]>([])
const signalErr = ref('')
const signalLoading = ref(false)

async function loadSignals() {
  if (!analysis.vtSymbol.value || analysis.isLoaded('signal')) return
  signalLoading.value = true
  signalErr.value = ''
  try {
    const vt = analysis.vtSymbol.value
    const results = await Promise.all(
      SIGNAL_MODES.map(async (m) => {
        const board = await watchlistApi.strategyBoard({ signalMode: m.id })
        return { m, row: board.signals.find((s) => s.vt_symbol === vt) }
      }),
    )
    signalRows.value = results
      .filter(
        (r): r is { m: { id: BoardSignalMode; label: string }; row: StrategySignalRow } => !!r.row,
      )
      .map((r) => ({ mode: r.m.label, row: r.row }))
    analysis.markLoaded('signal')
  } catch (e) {
    signalErr.value = e instanceof Error ? e.message : '策略信号加载失败'
  } finally {
    signalLoading.value = false
  }
}

function signalClass(sig: string) {
  if (sig === 'buy') return 'up'
  if (sig === 'sell') return 'down'
  return ''
}

const radarEntry = ref<{
  card_count: number
  card_titles: string[]
  resonance_score: number
  seal_time_label?: string
} | null>(null)
const radarErr = ref('')
const radarLoading = ref(false)

async function loadRadar() {
  if (!analysis.vtSymbol.value || analysis.isLoaded('radar')) return
  radarLoading.value = true
  radarErr.value = ''
  try {
    const vt = analysis.vtSymbol.value
    const resp = await marketApi.radarResonance({ top_n: 100, min_cards: 1 })
    radarEntry.value = resp.entries.find((e) => e.vt_symbol === vt) || null
    analysis.markLoaded('radar')
  } catch (e) {
    radarErr.value = e instanceof Error ? e.message : '雷达共振加载失败'
  } finally {
    radarLoading.value = false
  }
}

const aiMode = ref<'fast' | 'deep'>('fast')
const aiBusy = ref(false)
const aiStatus = ref('')
const aiReport = ref('')
const aiErr = ref('')
const aiConfigured = ref<boolean | null>(null)
const reportList = ref<TeamReportListItem[]>([])
const reportDetail = ref<TeamReport | null>(null)
const reportListErr = ref('')

async function checkAiStatus() {
  try {
    const st = await aiApi.status()
    aiConfigured.value = st.configured
  } catch {
    aiConfigured.value = false
  }
}

async function loadReportList() {
  if (!analysis.vtSymbol.value) return
  reportListErr.value = ''
  try {
    const page = await contentApi.teamReportsPage(analysis.vtSymbol.value, 1, 20)
    reportList.value = page.items
  } catch (e) {
    reportListErr.value = e instanceof Error ? e.message : '历史研报加载失败'
  }
}

async function openReport(id: number) {
  try {
    reportDetail.value = await contentApi.teamReport(id)
  } catch (e) {
    aiErr.value = e instanceof Error ? e.message : '研报详情加载失败'
  }
}

async function runAi() {
  const vt = analysis.vtSymbol.value
  if (!vt || aiBusy.value || !aiConfigured.value) return
  aiBusy.value = true
  aiErr.value = ''
  aiReport.value = ''
  aiStatus.value = aiMode.value === 'deep' ? '深度预取中…' : '预取中…'
  try {
    await aiApi.streamTeam(
      vt,
      {
        onEvent: (ev) => {
          if (ev.kind === 'started' && ev.agent && ev.agent !== 'system') {
            aiStatus.value = `${ev.label || ev.agent} 分析中…`
          }
          if (ev.kind === 'score' && ev.agent === 'system' && ev.weighted != null) {
            aiStatus.value =
              aiMode.value === 'deep'
                ? `加权 ${ev.weighted} · 三分析师并行中…`
                : `加权 ${ev.weighted} · 首席汇总中…`
          }
          if (ev.kind === 'delta' && ev.agent === 'chief' && ev.content) {
            aiStatus.value = '首席汇总中…'
            aiReport.value += ev.content
          }
          if (ev.kind === 'error') aiErr.value = ev.detail || '团队分析失败'
        },
        onReportSaved: () => {
          aiStatus.value = '研报已保存'
          void loadReportList()
        },
        onDone: () => {
          if (aiStatus.value) aiStatus.value = ''
        },
        onError: (err) => {
          aiErr.value = err
          aiStatus.value = ''
        },
      },
      undefined,
      aiMode.value,
    )
  } catch (e) {
    aiErr.value = e instanceof Error ? e.message : '团队分析失败'
  } finally {
    aiBusy.value = false
  }
}

const memo = ref<NoteMemo | null>(null)
const memoDraft = ref('')
const memoSaving = ref(false)
const memoErr = ref('')
const entries = ref<NoteEntry[]>([])
const entryDraft = ref('')
const entryErr = ref('')
const notesLoaded = ref(false)

async function loadNotes() {
  if (!analysis.vtSymbol.value || notesLoaded.value) return
  notesLoaded.value = true
  try {
    const vt = analysis.vtSymbol.value
    const [m, page] = await Promise.all([contentApi.memo(vt), contentApi.entriesPage(vt, 1, 50)])
    memo.value = m
    memoDraft.value = m.body || ''
    entries.value = page.items
  } catch (e) {
    memoErr.value = e instanceof Error ? e.message : '笔记加载失败'
  }
}

async function saveMemo() {
  if (!analysis.vtSymbol.value || memoSaving.value) return
  memoSaving.value = true
  memoErr.value = ''
  try {
    memo.value = await contentApi.saveMemo(analysis.vtSymbol.value, memoDraft.value.trim())
  } catch (e) {
    memoErr.value = e instanceof Error ? e.message : '速记保存失败'
  } finally {
    memoSaving.value = false
  }
}

async function addEntry() {
  const body = entryDraft.value.trim()
  if (!analysis.vtSymbol.value || !body) return
  entryErr.value = ''
  try {
    await contentApi.addEntry(analysis.vtSymbol.value, body)
    entryDraft.value = ''
    const page = await contentApi.entriesPage(analysis.vtSymbol.value, 1, 50)
    entries.value = page.items
  } catch (e) {
    entryErr.value = e instanceof Error ? e.message : '添加失败'
  }
}

async function removeEntry(id: number) {
  try {
    await contentApi.deleteEntry(id)
    entries.value = entries.value.filter((e) => e.id !== id)
  } catch (e) {
    entryErr.value = e instanceof Error ? e.message : '删除失败'
  }
}

function fmtAmount(v: number | null | undefined): string {
  if (v == null || Number.isNaN(v) || v <= 0) return '—'
  if (v >= 1e8) return (v / 1e8).toFixed(2) + '亿'
  if (v >= 1e4) return (v / 1e4).toFixed(1) + '万'
  return v.toFixed(0)
}

const SYNC_JOBS = [
  { id: 'sync_watchlist_financials', label: '同步财报', tab: 'fundamental' },
  { id: 'sync_disclosure_calendar', label: '同步披露计划', tab: 'fundamental' },
  { id: 'fill_watchlist_bars', label: '补全日 K', tab: 'quote' },
  { id: 'warm_watchlist_strategy_cache', label: '预热策略信号', tab: 'signal' },
] as const

const syncMenuOpen = ref(false)
const syncBusy = ref('')
const syncMsg = ref('')
const syncErr = ref('')

function closeSyncMenu() {
  syncMenuOpen.value = false
}

async function runSyncJob(jobId: string, tab: (typeof SYNC_JOBS)[number]['tab']) {
  if (syncBusy.value) return
  syncBusy.value = jobId
  syncMsg.value = ''
  syncErr.value = ''
  closeSyncMenu()
  try {
    const accepted = await opsApi.runJob(jobId)
    analysis.invalidate(tab)
    syncMsg.value = `已提交 ${accepted.kind}（${accepted.job_id}），稍后切回该页签即可看到更新。`
  } catch (e) {
    syncErr.value = e instanceof Error ? e.message : '提交同步任务失败'
  } finally {
    syncBusy.value = ''
  }
}

onMounted(() => {
  window.addEventListener('keydown', onKeydown)
})

onUnmounted(() => {
  window.removeEventListener('keydown', onKeydown)
})
</script>

<template>
  <Teleport to="body">
    <transition name="stock">
      <div v-if="analysis.isOpen.value" class="stock-overlay" @click.self="analysis.close()">
        <div
          class="stock-modal"
          role="dialog"
          aria-modal="true"
          aria-label="个股分析"
          @click.self="closeSyncMenu"
        >
          <div class="stock-head">
            <strong class="stock-title">{{ displayName }}</strong>
            <span class="stock-code mono">{{ analysis.vtSymbol.value }}</span>
            <div class="spacer"></div>
            <div class="sync-menu">
              <button
                type="button"
                class="icon-btn"
                :class="{ on: syncMenuOpen }"
                title="数据同步（Ops 任务）"
                :disabled="!!syncBusy"
                @click="syncMenuOpen = !syncMenuOpen"
              >
                <svg
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="2"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                >
                  <path d="M21 12a9 9 0 1 1-2.64-6.36" />
                  <path d="M21 3v6h-6" />
                </svg>
              </button>
              <div v-if="syncMenuOpen" class="sync-pop">
                <button
                  v-for="j in SYNC_JOBS"
                  :key="j.id"
                  type="button"
                  class="sync-item"
                  :disabled="syncBusy === j.id"
                  @click="runSyncJob(j.id, j.tab)"
                >
                  {{ syncBusy === j.id ? '提交中…' : j.label }}
                </button>
              </div>
            </div>
            <button type="button" class="icon-btn" title="关闭" @click="analysis.close()">
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

          <div class="stock-tabs">
            <button
              v-for="t in TABS"
              :key="t.key"
              type="button"
              :class="{ on: analysis.activeTab.value === t.key }"
              @click="switchTab(t.key)"
            >
              {{ t.label }}
            </button>
          </div>

          <div v-if="syncMsg" class="sync-banner ok">{{ syncMsg }}</div>
          <div v-if="syncErr" class="sync-banner err">{{ syncErr }}</div>

          <div class="stock-body">
            <div v-if="analysis.activeTab.value === 'quote'" class="quote-tab">
              <p v-if="quoteLoading" class="hint">加载行情…</p>
              <p v-else-if="quoteErr" class="err">{{ quoteErr }}</p>
              <template v-else-if="quote">
                <div class="price-hero">
                  <div class="price-main">
                    <span class="q-label">现价</span>
                    <span class="price-value">{{
                      quote.last_price ? quote.last_price.toFixed(2) : '—'
                    }}</span>
                  </div>
                  <div
                    class="price-chg"
                    :class="
                      (quote.change_pct || 0) > 0
                        ? 'up-bg'
                        : (quote.change_pct || 0) < 0
                          ? 'down-bg'
                          : ''
                    "
                  >
                    <span class="q-label">涨跌幅</span>
                    <span class="chg-value">{{
                      quote.change_pct != null
                        ? `${quote.change_pct > 0 ? '+' : ''}${quote.change_pct.toFixed(2)}%`
                        : '—'
                    }}</span>
                  </div>
                </div>
                <div class="quote-grid">
                  <div class="q-item">
                    <span class="q-label">换手%</span
                    ><span class="q-value">{{
                      quote.turnover_rate ? quote.turnover_rate.toFixed(2) : '—'
                    }}</span>
                  </div>
                  <div class="q-item">
                    <span class="q-label">量比</span
                    ><span class="q-value">{{
                      quote.volume_ratio ? quote.volume_ratio.toFixed(2) : '—'
                    }}</span>
                  </div>
                  <div class="q-item">
                    <span class="q-label">振幅%</span
                    ><span class="q-value">{{
                      quote.amplitude ? quote.amplitude.toFixed(2) : '—'
                    }}</span>
                  </div>
                  <div class="q-item">
                    <span class="q-label">成交量</span
                    ><span class="q-value">{{ fmtAmount(quote.volume) }}</span>
                  </div>
                  <div class="q-item">
                    <span class="q-label">成交额</span
                    ><span class="q-value">{{ fmtAmount(quote.amount) }}</span>
                  </div>
                  <div class="q-item">
                    <span class="q-label">行业</span
                    ><span class="q-value">{{ quote.industry || '—' }}</span>
                  </div>
                </div>
                <div class="bar-controls">
                  <div class="limits">
                    <button
                      type="button"
                      class="chip"
                      :class="{ on: barInterval === 'd' }"
                      @click="switchInterval('d')"
                    >
                      日K
                    </button>
                    <button
                      type="button"
                      class="chip"
                      :class="{ on: barInterval === '1m' }"
                      @click="switchInterval('1m')"
                    >
                      1分
                    </button>
                  </div>
                  <div class="limits">
                    <button
                      v-for="n in barLimitChoices"
                      :key="n"
                      type="button"
                      class="chip"
                      :class="{ on: barLimit === n }"
                      @click="switchBarLimit(n)"
                    >
                      {{ barInterval === '1m' ? `${n}根` : `${n}日` }}
                    </button>
                  </div>
                </div>
                <p v-if="barsLoading" class="hint">加载 K 线…</p>
                <p v-else-if="barsErr" class="err">{{ barsErr }}</p>
                <div v-else-if="bars.length" class="chart">
                  <CandleChart :bars="bars" :height="340" :interval="barInterval" />
                </div>
                <p v-else class="hint">暂无 K 线</p>
              </template>
              <p v-else class="hint">无行情数据</p>
            </div>

            <div v-if="analysis.activeTab.value === 'fundamental'" class="fund-tab">
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
                        · 同步 {{ fund.sync.last_sync_at }}</span
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

            <div v-if="analysis.activeTab.value === 'signal'" class="signal-tab">
              <p v-if="signalLoading" class="hint">加载策略信号…</p>
              <p v-else-if="signalErr" class="err">{{ signalErr }}</p>
              <template v-else-if="signalRows.length">
                <div class="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>模式</th>
                        <th>信号</th>
                        <th>强度</th>
                        <th>参考买</th>
                        <th>参考卖</th>
                        <th>摘要</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr v-for="s in signalRows" :key="s.mode">
                        <td>{{ s.mode }}</td>
                        <td>
                          <span class="signal-badge" :class="signalClass(s.row.signal)">{{
                            s.row.signal_label
                          }}</span>
                        </td>
                        <td>
                          <template v-if="s.row.strength_tier_label">
                            {{ s.row.strength_tier_label
                            }}<span v-if="s.row.strength != null">
                              · {{ s.row.strength.toFixed(1) }}</span
                            >
                          </template>
                          <template v-else>{{
                            s.row.strength != null ? s.row.strength.toFixed(0) : '—'
                          }}</template>
                        </td>
                        <td>
                          {{ s.row.ref_buy_price != null ? s.row.ref_buy_price.toFixed(2) : '—' }}
                        </td>
                        <td>
                          {{ s.row.ref_sell_price != null ? s.row.ref_sell_price.toFixed(2) : '—' }}
                        </td>
                        <td class="clip">{{ s.row.reason_summary || '—' }}</td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </template>
              <p v-else class="hint">无信号，可点右上角同步按钮预热策略信号。</p>
            </div>

            <div v-if="analysis.activeTab.value === 'radar'" class="radar-tab">
              <p v-if="radarLoading" class="hint">加载雷达共振…</p>
              <p v-else-if="radarErr" class="err">{{ radarErr }}</p>
              <template v-else-if="radarEntry">
                <div class="radar-summary">
                  <div class="q-item">
                    <span class="q-label">共振分</span
                    ><span class="q-value">{{ radarEntry.resonance_score.toFixed(1) }}</span>
                  </div>
                  <div class="q-item">
                    <span class="q-label">卡片数</span
                    ><span class="q-value">{{ radarEntry.card_count }}</span>
                  </div>
                  <div v-if="radarEntry.seal_time_label" class="q-item">
                    <span class="q-label">封板</span
                    ><span class="q-value">{{ radarEntry.seal_time_label }}</span>
                  </div>
                </div>
                <div v-if="radarEntry.card_titles.length" class="card-titles">
                  <span v-for="t in radarEntry.card_titles" :key="t" class="chip-tag">{{ t }}</span>
                </div>
                <p v-else class="hint">暂无卡片标题</p>
              </template>
              <p v-else class="hint">暂无共振</p>
            </div>

            <div v-if="analysis.activeTab.value === 'ai'" class="ai-tab">
              <p v-if="aiConfigured === false" class="warn-banner">
                未配置 LLM_API_KEY，团队分析不可用。
              </p>
              <div class="ai-controls">
                <div class="team-mode">
                  <label :class="{ on: aiMode === 'fast' }">
                    <input v-model="aiMode" type="radio" value="fast" :disabled="aiBusy" />
                    <span>快速</span>
                  </label>
                  <label :class="{ on: aiMode === 'deep' }">
                    <input v-model="aiMode" type="radio" value="deep" :disabled="aiBusy" />
                    <span>深度</span>
                  </label>
                </div>
                <button
                  type="button"
                  class="primary"
                  :disabled="aiBusy || aiConfigured === false"
                  @click="runAi"
                >
                  {{ aiBusy ? '分析中…' : aiMode === 'deep' ? '深度团队分析' : '团队分析' }}
                </button>
              </div>
              <p v-if="aiStatus" class="hint">{{ aiStatus }}</p>
              <p v-if="aiErr" class="err">{{ aiErr }}</p>
              <div v-if="aiReport" class="report-body">
                <MarkdownView :source="aiReport" />
              </div>

              <section class="report-section">
                <div class="block-head">
                  <h4>历史研报</h4>
                </div>
                <p v-if="reportListErr" class="err">{{ reportListErr }}</p>
                <div v-else-if="reportList.length" class="report-list">
                  <button
                    v-for="r in reportList"
                    :key="r.id"
                    type="button"
                    class="report-item"
                    :class="{ on: reportDetail?.id === r.id }"
                    @click="openReport(r.id)"
                  >
                    <span class="report-title">{{ r.title }}</span>
                    <span class="muted tiny">{{ r.mode }} · {{ r.created_at }}</span>
                  </button>
                </div>
                <p v-else class="hint">暂无历史研报，可点击上方生成。</p>
                <div v-if="reportDetail" class="report-detail">
                  <h5>{{ reportDetail.title }}</h5>
                  <MarkdownView :source="reportDetail.body" />
                </div>
              </section>
            </div>

            <div v-if="analysis.activeTab.value === 'notes'" class="notes-tab">
              <section class="notes-card">
                <div class="block-head">
                  <h4>速记</h4>
                </div>
                <textarea v-model="memoDraft" rows="3" placeholder="记录该标的要点…"></textarea>
                <button type="button" class="primary" :disabled="memoSaving" @click="saveMemo">
                  {{ memoSaving ? '保存中…' : '保存速记' }}
                </button>
                <p v-if="memoErr" class="err">{{ memoErr }}</p>
              </section>
              <section class="notes-card">
                <div class="block-head">
                  <h4>流水</h4>
                </div>
                <div class="entry-add">
                  <input v-model="entryDraft" placeholder="追加一条流水" @keyup.enter="addEntry" />
                  <button type="button" class="ghost" @click="addEntry">添加</button>
                </div>
                <p v-if="entryErr" class="err">{{ entryErr }}</p>
                <div v-if="entries.length" class="entry-list">
                  <div v-for="e in entries" :key="e.id" class="entry">
                    <div class="entry-body">{{ e.body }}</div>
                    <div class="entry-foot">
                      <span class="muted tiny">{{ e.created_at }}</span>
                      <button type="button" class="link" @click="removeEntry(e.id)">删</button>
                    </div>
                  </div>
                </div>
                <p v-else class="hint">暂无流水。</p>
              </section>
            </div>
          </div>
        </div>
      </div>
    </transition>
  </Teleport>
</template>

<style scoped>
/* ---------- 遮罩与弹窗骨架 ---------- */
.stock-overlay {
  position: fixed;
  inset: 0;
  z-index: 1000;
  display: grid;
  place-items: center;
  background: rgba(15, 15, 15, 0.42);
  backdrop-filter: blur(3px);
  -webkit-backdrop-filter: blur(3px);
  padding: 24px;
}
.stock-enter-active,
.stock-leave-active {
  transition:
    opacity 0.22s ease,
    transform 0.22s ease;
}
.stock-enter-from,
.stock-leave-to {
  opacity: 0;
}
.stock-enter-from .stock-modal,
.stock-leave-to .stock-modal {
  transform: translateY(10px) scale(0.98);
}
.stock-modal {
  width: 100%;
  max-width: 920px;
  max-height: 88vh;
  display: grid;
  grid-template-rows: auto auto auto 1fr;
  gap: 12px;
  padding: 18px 20px;
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: 1rem;
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.16);
}

/* ---------- 头部 ---------- */
.stock-head {
  display: flex;
  align-items: center;
  gap: 10px;
}
.stock-title {
  font-size: 1.08rem;
  font-weight: 700;
  color: var(--ink);
  letter-spacing: 0.01em;
}
.stock-code {
  font-size: 0.76rem;
  color: var(--brand);
  background: var(--brand-light);
  border: 1px solid var(--brand-soft);
  border-radius: 999px;
  padding: 2px 10px;
  font-family: var(--mono);
}
.stock-head .spacer {
  flex: 1;
}

/* ---------- 图标按钮 ---------- */
.icon-btn {
  display: inline-grid;
  place-items: center;
  width: 30px;
  height: 30px;
  padding: 0;
  border: 1px solid var(--line);
  border-radius: 0.5rem;
  background: transparent;
  color: var(--ink-muted);
  cursor: pointer;
  transition:
    background 0.15s ease,
    border-color 0.15s ease,
    color 0.15s ease;
}
.icon-btn:hover {
  background: var(--surface-muted);
  border-color: var(--brand-soft);
  color: var(--brand);
}
.icon-btn.on {
  background: var(--brand-light);
  border-color: var(--brand-soft);
  color: var(--brand);
}
.icon-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.icon-btn svg {
  width: 16px;
  height: 16px;
}

/* ---------- 同步下拉 ---------- */
.sync-menu {
  position: relative;
}
.sync-pop {
  position: absolute;
  right: 0;
  top: calc(100% + 6px);
  z-index: 20;
  min-width: 158px;
  display: grid;
  gap: 2px;
  padding: 5px;
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: 0.625rem;
  box-shadow: var(--shadow-panel);
}
.sync-item {
  background: transparent;
  border: none;
  color: var(--text);
  text-align: left;
  padding: 7px 10px;
  border-radius: 0.4rem;
  font-size: 0.82rem;
  cursor: pointer;
  white-space: nowrap;
  transition:
    background 0.12s ease,
    color 0.12s ease;
}
.sync-item:hover {
  background: var(--brand-light);
  color: var(--brand);
}
.sync-item:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* ---------- 同步提示条 ---------- */
.sync-banner {
  margin: 0;
  padding: 7px 12px;
  border-radius: 0.6rem;
  font-size: 0.78rem;
  border: 1px solid var(--line);
  background: var(--surface-muted);
}
.sync-banner.ok {
  color: var(--ok);
}
.sync-banner.err {
  color: var(--danger);
}

/* ---------- 页签（分段控件） ---------- */
.stock-tabs {
  display: flex;
  gap: 2px;
  padding: 3px;
  background: var(--surface-muted);
  border: 1px solid var(--line);
  border-radius: 0.7rem;
  overflow-x: auto;
}
.stock-tabs button {
  flex: 1 1 0;
  min-width: max-content;
  background: transparent;
  border: none;
  color: var(--muted);
  border-radius: 0.5rem;
  padding: 7px 14px;
  font-size: 0.82rem;
  cursor: pointer;
  white-space: nowrap;
  transition:
    background 0.15s ease,
    color 0.15s ease,
    box-shadow 0.15s ease;
}
.stock-tabs button:hover {
  color: var(--ink);
}
.stock-tabs button.on {
  background: var(--surface);
  color: var(--brand);
  font-weight: 600;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.08);
}

/* ---------- 内容区 ---------- */
.stock-body {
  min-height: 0;
  overflow: auto;
  display: grid;
  gap: 14px;
  padding-right: 2px;
}

/* ---------- 通用小工具 ---------- */
.mono {
  font-family: var(--mono);
}
.muted {
  color: var(--muted);
}
.tiny {
  font-size: 0.72rem;
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
.up {
  color: var(--danger);
}
.down {
  color: var(--ok);
}

/* ---------- 区块标题 ---------- */
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

/* ---------- 行情页 ---------- */
.quote-tab {
  display: grid;
  gap: 12px;
}
.price-hero {
  display: grid;
  grid-template-columns: 1.3fr 1fr;
  gap: 10px;
}
.price-main,
.price-chg {
  display: grid;
  gap: 3px;
  padding: 14px 16px;
  border-radius: 0.75rem;
  border: 1px solid var(--line);
  background: var(--surface-muted);
}
.price-main .q-label,
.price-chg .q-label {
  color: var(--muted);
  font-size: 0.75rem;
}
.price-value {
  font-size: 1.9rem;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  line-height: 1.1;
  color: var(--ink);
}
.price-chg {
  border-color: var(--border);
}
.price-chg.up-bg {
  background: rgba(225, 29, 72, 0.08);
  border-color: rgba(225, 29, 72, 0.25);
}
.price-chg.down-bg {
  background: rgba(22, 163, 74, 0.08);
  border-color: rgba(22, 163, 74, 0.25);
}
.chg-value {
  font-size: 1.6rem;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  line-height: 1.1;
}
.up-bg .chg-value {
  color: var(--danger);
}
.down-bg .chg-value {
  color: var(--ok);
}
.quote-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(110px, 1fr));
  gap: 8px;
}
.q-item {
  display: grid;
  gap: 2px;
  padding: 10px 12px;
  border: 1px solid var(--line);
  border-radius: 0.65rem;
  background: var(--surface);
}
.q-label {
  color: var(--muted);
  font-size: 0.72rem;
}
.q-value {
  font-size: 0.95rem;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
  color: var(--ink);
}
.bar-controls {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
  padding: 8px 2px;
}
.limits {
  display: flex;
  gap: 4px;
  align-items: center;
}
.chip {
  background: transparent;
  border: 1px solid var(--line);
  color: var(--muted);
  border-radius: 999px;
  padding: 4px 12px;
  font-size: 0.75rem;
  cursor: pointer;
  transition:
    background 0.12s ease,
    color 0.12s ease,
    border-color 0.12s ease;
}
.chip:hover {
  border-color: var(--brand-soft);
  color: var(--ink);
}
.chip.on {
  background: var(--brand-light);
  color: var(--brand);
  border-color: var(--brand-soft);
  font-weight: 500;
}
.chart :deep(.candle svg) {
  height: 340px;
}

/* ---------- 基本面页 ---------- */
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

/* ---------- 策略信号页 ---------- */
.table-wrap {
  border: 1px solid var(--line);
  border-radius: 0.75rem;
  overflow: auto;
  background: var(--surface);
  box-shadow: var(--shadow-card);
}
.table-wrap th,
.table-wrap td {
  padding: 9px 10px;
  border-bottom: 1px solid var(--border);
  font-size: 0.85rem;
  text-align: left;
  white-space: nowrap;
}
.table-wrap tbody tr:last-child td {
  border-bottom: none;
}
.table-wrap th {
  color: var(--muted);
  font-weight: 500;
  background: var(--surface-muted);
  position: sticky;
  top: 0;
}
.table-wrap .clip {
  max-width: 280px;
  overflow: hidden;
  text-overflow: ellipsis;
}
.signal-badge {
  display: inline-flex;
  align-items: center;
  padding: 2px 10px;
  border-radius: 999px;
  font-size: 0.75rem;
  font-weight: 600;
}
.signal-badge.up {
  background: rgba(225, 29, 72, 0.1);
  color: var(--danger);
}
.signal-badge.down {
  background: rgba(22, 163, 74, 0.1);
  color: var(--ok);
}

/* ---------- 雷达页 ---------- */
.radar-summary {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(130px, 1fr));
  gap: 8px;
}
.card-titles {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.chip-tag {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  border: 1px solid var(--border);
  border-radius: 999px;
  padding: 3px 10px;
  font-size: 0.78rem;
  background: var(--surface-muted);
  color: var(--ink);
}

/* ---------- AI 研报页 ---------- */
.ai-controls {
  display: flex;
  gap: 10px;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  padding: 10px 12px;
  border: 1px solid var(--line);
  border-radius: 0.65rem;
  background: var(--surface-muted);
}
.team-mode {
  display: inline-flex;
  gap: 8px;
}
.team-mode label {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 0.82rem;
  color: var(--muted);
  cursor: pointer;
}
.team-mode label.on {
  color: var(--brand);
  font-weight: 500;
}
.primary {
  background: var(--accent);
  color: var(--brand-foreground);
  border: none;
  border-radius: 0.5rem;
  padding: 8px 14px;
  font-weight: 600;
  cursor: pointer;
  transition:
    background 0.15s ease,
    opacity 0.15s ease;
}
.primary:hover:not(:disabled) {
  background: var(--accent-hover);
}
.primary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.warn-banner {
  margin: 0;
  padding: 9px 12px;
  border: 1px solid rgba(225, 29, 72, 0.25);
  border-radius: 0.6rem;
  background: rgba(225, 29, 72, 0.06);
  color: var(--danger);
  font-size: 0.82rem;
}
.report-section {
  display: grid;
  gap: 10px;
}
.report-section h4 {
  margin: 0;
  font-size: 0.88rem;
  font-weight: 600;
}
.report-list {
  display: grid;
  gap: 5px;
}
.report-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  background: var(--surface-muted);
  border: 1px solid var(--border);
  border-radius: 0.5rem;
  padding: 7px 11px;
  text-align: left;
  cursor: pointer;
  color: var(--text);
  font-size: 0.82rem;
  transition:
    border-color 0.12s ease,
    background 0.12s ease,
    color 0.12s ease;
}
.report-item:hover,
.report-item.on {
  border-color: var(--brand-soft);
  background: var(--brand-light);
  color: var(--brand);
}
.report-title {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.report-detail {
  border: 1px solid var(--line);
  border-radius: 0.75rem;
  padding: 12px 14px;
  background: var(--surface-muted);
}
.report-detail h5 {
  margin: 0 0 8px;
  font-size: 0.9rem;
}
.report-body :deep(.markdown) {
  font-size: 0.82rem;
  line-height: 1.5;
}
.report-detail :deep(.markdown) {
  font-size: 0.82rem;
  line-height: 1.5;
}

/* ---------- 笔记页 ---------- */
.notes-tab {
  display: grid;
  gap: 12px;
}
.notes-card {
  display: grid;
  gap: 9px;
  border: 1px solid var(--line);
  border-radius: 0.75rem;
  background: var(--surface);
  padding: 14px 16px;
  box-shadow: var(--shadow-card);
}
.notes-card textarea {
  width: 100%;
  border: 1px solid var(--border);
  border-radius: 0.5rem;
  background: var(--bg-elevated);
  color: var(--text);
  padding: 9px 11px;
  resize: vertical;
  font-family: inherit;
  font-size: 0.85rem;
}
.entry-add {
  display: flex;
  gap: 8px;
}
.entry-add input {
  flex: 1;
  border: 1px solid var(--border);
  border-radius: 0.5rem;
  background: var(--bg-elevated);
  color: var(--text);
  padding: 8px 11px;
}
.ghost {
  background: transparent;
  border: 1px solid var(--border);
  color: var(--text);
  border-radius: 0.5rem;
  padding: 7px 12px;
  cursor: pointer;
  transition:
    background 0.12s ease,
    color 0.12s ease,
    border-color 0.12s ease;
}
.ghost:hover {
  background: var(--brand-light);
  color: var(--brand);
  border-color: var(--brand-soft);
}
.entry-list {
  display: grid;
  gap: 5px;
}
.entry {
  border: 1px solid var(--border);
  border-radius: 0.5rem;
  padding: 8px 11px;
  background: var(--surface-muted);
  display: grid;
  gap: 4px;
}
.entry-body {
  font-size: 0.85rem;
}
.entry-foot {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.link {
  background: none;
  border: none;
  color: var(--muted);
  padding: 0;
  cursor: pointer;
}
.link:hover {
  color: var(--danger);
}

@media (max-width: 560px) {
  .price-hero {
    grid-template-columns: 1fr;
  }
  .fund-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>

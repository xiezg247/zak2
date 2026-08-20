<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { useStockAnalysis } from '../composables/useStockAnalysis'
import { watchlistApi, type QuoteOut } from '../../../api/watchlist'

const analysis = useStockAnalysis()

const quote = ref<QuoteOut | null>(null)
const quoteErr = ref('')
const quoteLoading = ref(false)

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

function fmtAmount(v: number | null | undefined): string {
  if (v == null || Number.isNaN(v) || v <= 0) return '—'
  if (v >= 1e8) return (v / 1e8).toFixed(2) + '亿'
  if (v >= 1e4) return (v / 1e4).toFixed(1) + '万'
  return v.toFixed(0)
}

onMounted(() => {
  if (analysis.vtSymbol.value) void loadQuote()
})

watch(
  () => analysis.activeTab.value,
  (tab) => {
    if (tab === 'quote' && analysis.vtSymbol.value && !analysis.isLoaded('quote')) void loadQuote()
  },
)

watch(
  () => analysis.vtSymbol.value,
  (vt) => {
    if (vt) void loadQuote()
  },
)
</script>

<template>
  <div class="quote-tab">
    <p v-if="quoteLoading" class="hint">加载行情…</p>
    <p v-else-if="quoteErr" class="err">{{ quoteErr }}</p>
    <template v-else-if="quote">
      <div class="price-hero">
        <div class="price-main">
          <span class="q-label">现价</span>
          <span class="price-value">{{ quote.last_price ? quote.last_price.toFixed(2) : '—' }}</span>
        </div>
        <div
          class="price-chg"
          :class="
            (quote.change_pct || 0) > 0 ? 'up-bg' : (quote.change_pct || 0) < 0 ? 'down-bg' : ''
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
          <span class="q-label">换手%</span>
          <span class="q-value">{{
            quote.turnover_rate ? quote.turnover_rate.toFixed(2) : '—'
          }}</span>
        </div>
        <div class="q-item">
          <span class="q-label">量比</span>
          <span class="q-value">{{
            quote.volume_ratio ? quote.volume_ratio.toFixed(2) : '—'
          }}</span>
        </div>
        <div class="q-item">
          <span class="q-label">振幅%</span>
          <span class="q-value">{{ quote.amplitude ? quote.amplitude.toFixed(2) : '—' }}</span>
        </div>
        <div class="q-item">
          <span class="q-label">成交量</span>
          <span class="q-value">{{ fmtAmount(quote.volume) }}</span>
        </div>
        <div class="q-item">
          <span class="q-label">成交额</span>
          <span class="q-value">{{ fmtAmount(quote.amount) }}</span>
        </div>
        <div class="q-item">
          <span class="q-label">行业</span>
          <span class="q-value">{{ quote.industry || '—' }}</span>
        </div>
      </div>
    </template>
    <p v-else class="hint">无行情数据</p>
  </div>
</template>

<style scoped>
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

@media (max-width: 560px) {
  .price-hero {
    grid-template-columns: 1fr;
  }
}
</style>

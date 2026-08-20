<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import CandleChart from './CandleChart.vue'
import { watchlistApi, type Bar } from '../api/watchlist'

const vt = defineModel<string>('vt', { default: '' })

const props = defineProps<{
  name?: string
}>()

const bars = ref<Bar[]>([])
const error = ref('')
const loading = ref(false)
const barInterval = ref<'d' | '1m'>('d')
const barLimitDaily = ref(90)
const barLimit1m = ref(480)

const barLimit = computed({
  get: () => (barInterval.value === '1m' ? barLimit1m.value : barLimitDaily.value),
  set: (n: number) => {
    if (barInterval.value === '1m') barLimit1m.value = n
    else barLimitDaily.value = n
  },
})

const barLimitChoices = computed(() =>
  barInterval.value === '1m' ? [240, 480, 1200] : [60, 90, 120],
)

const title = computed(() => props.name?.trim() || vt.value)

async function loadBars() {
  const symbol = vt.value
  error.value = ''
  bars.value = []
  if (!symbol) {
    loading.value = false
    return
  }
  loading.value = true
  try {
    const resp = await watchlistApi.bars(symbol, barInterval.value, barLimit.value)
    bars.value = resp.bars
  } catch (e) {
    error.value = e instanceof Error ? e.message : '无 K 线'
  } finally {
    loading.value = false
  }
}

function close() {
  vt.value = ''
  bars.value = []
  error.value = ''
  loading.value = false
}

watch(vt, (v) => {
  if (v) void loadBars()
  else {
    bars.value = []
    error.value = ''
    loading.value = false
  }
})

watch([barLimit, barInterval], () => {
  if (vt.value) void loadBars()
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
      <div class="chart-modal" role="dialog" aria-modal="true" aria-label="K线图">
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
        <div class="bar-controls">
          <div class="limits">
            <button
              type="button"
              class="chip"
              :class="{ on: barInterval === 'd' }"
              @click="barInterval = 'd'"
            >
              日K
            </button>
            <button
              type="button"
              class="chip"
              :class="{ on: barInterval === '1m' }"
              @click="barInterval = '1m'"
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
              @click="barLimit = n"
            >
              {{ barInterval === '1m' ? `${n}根` : `${n}日` }}
            </button>
          </div>
        </div>
        <p v-if="loading" class="muted">
          {{ barInterval === '1m' ? '加载 1 分 K…' : '加载日 K…' }}
        </p>
        <template v-else-if="error">
          <p class="err">
            {{ error }}
            <RouterLink to="/ops" class="draft-link">{{
              barInterval === '1m' ? '去 Ops 补全 1 分 K' : '去 Ops 补全日 K'
            }}</RouterLink>
          </p>
        </template>
        <template v-else-if="!bars.length">
          <p class="muted">
            {{ barInterval === '1m' ? '暂无 1 分 K' : '暂无日 K' }}
            <RouterLink to="/ops" class="draft-link">{{
              barInterval === '1m' ? '去 Ops 补全 1 分 K' : '去 Ops 补全日 K'
            }}</RouterLink>
          </p>
        </template>
        <div v-else class="chart">
          <CandleChart :bars="bars" :height="400" :interval="barInterval" />
        </div>
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
  display: grid;
  gap: 12px;
  padding: 16px 18px;
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: 0.875rem;
  box-shadow: var(--shadow-panel);
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
.chart-modal :deep(.candle svg) {
  height: 400px;
}
.bar-controls {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}
.chart {
  border-top: 1px solid var(--border);
  padding-top: 8px;
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
.chip {
  background: transparent;
  border: 1px solid var(--border);
  color: var(--muted);
  border-radius: 0.5rem;
  padding: 4px 8px;
  font-size: 0.75rem;
  cursor: pointer;
}
.chip.on {
  background: var(--brand-light);
  color: var(--brand);
  border-color: var(--brand-soft);
  font-weight: 500;
}
.limits {
  display: flex;
  gap: 4px;
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

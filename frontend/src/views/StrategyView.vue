<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import AppShell from '../components/AppShell.vue'
import { backtestApi, type StrategyInfo } from '../api/backtest'

const router = useRouter()

const strategies = ref<StrategyInfo[]>([])
const strategiesError = ref('')

const CATEGORY_META: Record<string, { title: string; desc: string }> = {
  trend: { title: '趋势跟踪', desc: '顺势持有，捕捉主升段' },
  breakout: { title: '突破跟踪', desc: '新高 / 波动率突破，追强趋势' },
  reversion: { title: '均值回归', desc: '震荡低吸高抛，赚均值回归' },
}
const CATEGORY_ORDER = ['trend', 'breakout', 'reversion']

const grouped = computed(() =>
  CATEGORY_ORDER.filter((c) => strategies.value.some((s) => (s.category || 'trend') === c)).map(
    (c) => ({
      category: c,
      meta: CATEGORY_META[c] || { title: c, desc: '' },
      items: strategies.value.filter((s) => (s.category || 'trend') === c),
    }),
  ),
)

async function load() {
  try {
    strategies.value = await backtestApi.strategies()
  } catch (e) {
    strategiesError.value = e instanceof Error ? e.message : '回测策略加载失败'
  }
}

function gotoBacktestStrategy(strategyId: string) {
  void router.push({ path: '/backtest', query: { strategy: strategyId } })
}

onMounted(() => {
  void load()
})
</script>

<template>
  <AppShell title="策略" subtitle="回测策略清单" active="strategies">
    <div class="page">
      <p v-if="strategiesError" class="err">{{ strategiesError }}</p>
      <template v-else-if="strategies.length">
        <section v-for="g in grouped" :key="g.category" class="cat-block">
          <div class="cat-head">
            <h3>{{ g.meta.title }}</h3>
            <p class="cat-desc muted">{{ g.meta.desc }}</p>
            <span class="count">{{ g.items.length }}</span>
          </div>
          <div class="bt-grid">
            <div
              v-for="s in g.items"
              :key="s.id"
              class="bt-card"
              :class="{ featured: s.featured, [`cat-${g.category}`]: true }"
            >
              <div class="card-head">
                <div class="name">{{ s.name }}</div>
                <div class="tags">
                  <span v-for="t in s.tags || []" :key="t" class="tag">{{ t }}</span>
                </div>
              </div>
              <div v-if="s.default_params" class="params mono">{{ s.default_params }}</div>
              <p class="desc muted">{{ s.description }}</p>
              <p v-if="s.scenario" class="scenario">
                <span class="scenario-k">适用场景</span>{{ s.scenario }}
              </p>
              <div class="card-actions">
                <button type="button" class="ghost tiny-btn" @click="gotoBacktestStrategy(s.id)">
                  去回测
                </button>
              </div>
            </div>
          </div>
        </section>
      </template>
      <p v-else class="s muted">加载中…</p>
    </div>
  </AppShell>
</template>

<style scoped>
.page {
  display: grid;
  gap: 22px;
}
.cat-block {
  display: grid;
  gap: 10px;
}
.cat-head {
  display: flex;
  align-items: baseline;
  gap: 10px;
}
.cat-head h3 {
  margin: 0;
  font-size: 1rem;
  font-weight: 600;
  letter-spacing: 0.01em;
}
.cat-desc {
  margin: 0;
  font-size: 0.8rem;
}
.count {
  margin-left: auto;
  color: var(--ink-faint);
  font-size: 0.75rem;
  font-family: var(--mono);
}
.bt-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 12px;
}
.bt-card {
  border: 1px solid var(--line);
  border-radius: 0.9rem;
  background: var(--surface);
  box-shadow: var(--shadow-card);
  padding: 14px 16px;
  display: grid;
  gap: 8px;
  align-content: start;
  transition:
    transform 0.15s ease,
    box-shadow 0.15s ease,
    border-color 0.15s ease;
}
.bt-card:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-panel);
  border-color: var(--brand-soft);
}
.bt-card.featured {
  grid-column: span 2;
  background: linear-gradient(135deg, var(--brand-light), var(--surface) 55%);
  border-color: var(--brand-soft);
}
.card-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
}
.name {
  font-size: 0.98rem;
  font-weight: 600;
  color: var(--ink);
}
.tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}
.tag {
  display: inline-block;
  border: 1px solid var(--line);
  border-radius: 999px;
  padding: 1px 8px;
  font-size: 0.7rem;
  white-space: nowrap;
}
.cat-trend .tag {
  background: var(--brand-light);
  border-color: var(--brand-soft);
  color: var(--brand);
}
.cat-breakout .tag {
  background: rgba(22, 163, 74, 0.08);
  border-color: rgba(22, 163, 74, 0.25);
  color: var(--ok);
}
.cat-reversion .tag {
  background: rgba(115, 115, 115, 0.1);
  border-color: var(--line);
  color: var(--ink-muted);
}
.params {
  font-size: 0.78rem;
  color: var(--brand);
  background: var(--surface);
  border: 1px dashed var(--line);
  border-radius: 0.5rem;
  padding: 3px 8px;
  width: fit-content;
}
.desc {
  margin: 0;
  font-size: 0.8rem;
  line-height: 1.55;
}
.scenario {
  margin: 0;
  font-size: 0.8rem;
  line-height: 1.55;
  color: var(--ink-muted);
}
.scenario-k {
  display: inline-block;
  border: 1px solid var(--brand-soft);
  background: var(--brand-light);
  color: var(--brand);
  border-radius: 999px;
  padding: 0 6px;
  margin-right: 6px;
  font-size: 0.7rem;
  vertical-align: 1px;
}
.card-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 2px;
}
.ghost {
  background: transparent;
  border: 1px solid var(--border);
  color: var(--text);
  border-radius: 0.5rem;
  padding: 6px 10px;
  cursor: pointer;
}
.ghost:hover:not(:disabled) {
  background: var(--brand-light);
  color: var(--brand);
  border-color: var(--brand-soft);
}
.ghost:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.tiny-btn {
  padding: 4px 10px;
  font-size: 0.8rem;
}
.muted {
  color: var(--muted);
}
.mono {
  font-family: var(--mono);
}
.s {
  font-size: 0.85rem;
}
.err {
  margin: 0;
  color: var(--danger);
  font-size: 0.85rem;
}
@media (max-width: 900px) {
  .bt-card.featured {
    grid-column: span 1;
  }
  .card-head {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>

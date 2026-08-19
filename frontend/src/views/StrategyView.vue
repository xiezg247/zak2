<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import AppShell from '../components/AppShell.vue'
import { backtestApi, type StrategyInfo } from '../api/backtest'

const router = useRouter()

const strategies = ref<StrategyInfo[]>([])
const strategiesError = ref('')

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
      <section class="card">
        <h3>回测策略</h3>
        <p v-if="strategiesError" class="err">{{ strategiesError }}</p>
        <div v-else-if="strategies.length" class="bt-grid">
          <div v-for="s in strategies" :key="s.id" class="bt-card">
            <div class="k">{{ s.name }}</div>
            <p class="s muted">{{ s.description }}</p>
            <p class="s mono muted">interval {{ s.interval }} · {{ s.engine }}</p>
            <div class="card-actions">
              <button type="button" class="ghost tiny-btn" @click="gotoBacktestStrategy(s.id)">
                去回测
              </button>
            </div>
          </div>
        </div>
        <p v-else class="s muted">加载中…</p>
      </section>
    </div>
  </AppShell>
</template>

<style scoped>
.page {
  display: grid;
  gap: 14px;
}
.card {
  border: 1px solid var(--line);
  border-radius: 0.75rem;
  background: var(--surface);
  box-shadow: var(--shadow-card);
  padding: 14px 16px;
  display: grid;
  gap: 2px;
  align-content: start;
}
.card h3 {
  margin: 0 0 10px;
  font-size: 0.9rem;
  font-weight: 600;
}
.k {
  color: var(--muted);
  font-size: 0.78rem;
  font-weight: 500;
  letter-spacing: 0.02em;
}
.s {
  margin-top: 4px;
  font-size: 0.8rem;
}
.card-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 8px;
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
  padding: 4px 8px;
  font-size: 0.8rem;
}
.bt-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 10px;
}
.bt-card {
  border: 1px solid var(--line);
  border-radius: 0.75rem;
  background: var(--surface-muted);
  padding: 12px 14px;
  display: grid;
  gap: 2px;
  align-content: start;
}
.muted {
  color: var(--muted);
}
.err {
  margin: 0;
  color: var(--danger);
  font-size: 0.85rem;
}
</style>

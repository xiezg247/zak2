<script setup lang="ts">
import { computed, ref } from 'vue'
import type { BacktestRun, OptimizeSummary } from '../../../api/backtest'

const props = defineProps<{
  selected: BacktestRun | null
  compare: BacktestRun[]
  optimizeSummary: OptimizeSummary | null
  loading: boolean
}>()

const emit = defineEmits<{
  openRun: [id: string]
}>()

const showAllTrades = ref(false)

function numStat(key: string): number | null {
  const v = props.selected?.statistics?.[key]
  return typeof v === 'number' ? v : null
}

const displayedTrades = computed(() => {
  const trades = props.selected?.trades || []
  return showAllTrades.value ? trades : trades.slice(0, 40)
})

const spark = computed(() => {
  const curve = props.selected?.equity_curve || []
  if (curve.length < 2) return ''
  const vals = curve.map((p) => p.equity)
  const min = Math.min(...vals)
  const max = Math.max(...vals)
  const span = max - min || 1
  const w = 360
  const h = 120
  return vals
    .map((v, i) => {
      const x = (i / (vals.length - 1)) * w
      const y = h - ((v - min) / span) * (h - 8) - 4
      return `${x.toFixed(1)},${y.toFixed(1)}`
    })
    .join(' ')
})
</script>

<template>
  <section class="right">
    <div v-if="selected" class="detail">
      <h2>
        {{ selected.vt_symbol }} · {{ selected.strategy }}
        <span class="muted"> · {{ selected.interval === '1m' ? '1m' : '日 K' }}</span>
        <span v-if="selected.engine" class="muted"> · {{ selected.engine }}</span>
        <span v-if="selected.status === 'failed'" class="muted"> · 失败</span>
      </h2>
      <p v-if="selected.interval === '1m'" class="hint muted">
        分钟回测：夏普/年化等仍按引擎日度统计口径，解读时注意样本跨度。
      </p>
      <p v-if="selected.error_message" class="err">{{ selected.error_message }}</p>
      <div class="stats">
        <div class="stat">
          <div class="k">收益%</div>
          <div
            class="v"
            :class="{
              up: (selected.total_return || 0) > 0,
              down: (selected.total_return || 0) < 0,
            }"
          >
            {{ selected.total_return != null ? selected.total_return.toFixed(2) : '—' }}
          </div>
        </div>
        <div class="stat">
          <div class="k">最大回撤%</div>
          <div class="v">
            {{ selected.max_drawdown != null ? selected.max_drawdown.toFixed(2) : '—' }}
          </div>
        </div>
        <div class="stat">
          <div class="k">夏普</div>
          <div class="v">
            {{ selected.sharpe_ratio != null ? selected.sharpe_ratio.toFixed(2) : '—' }}
          </div>
        </div>
        <div class="stat">
          <div class="k">成交</div>
          <div class="v">{{ selected.trade_count ?? '—' }}</div>
        </div>
        <div v-if="numStat('annual_return') != null" class="stat">
          <div class="k">年化%</div>
          <div class="v">{{ numStat('annual_return')!.toFixed(2) }}</div>
        </div>
        <div v-if="numStat('return_std') != null" class="stat">
          <div class="k">波动%</div>
          <div class="v">{{ numStat('return_std')!.toFixed(2) }}</div>
        </div>
        <div v-if="numStat('win_rate') != null" class="stat">
          <div class="k">胜率</div>
          <div class="v">{{ numStat('win_rate')!.toFixed(2) }}</div>
        </div>
        <div v-if="numStat('profit_loss_ratio') != null" class="stat">
          <div class="k">盈亏比</div>
          <div class="v">{{ numStat('profit_loss_ratio')!.toFixed(2) }}</div>
        </div>
      </div>
      <div v-if="spark" class="chart">
        <svg viewBox="0 0 360 120" preserveAspectRatio="none">
          <polyline fill="none" stroke="var(--brand)" stroke-width="2" :points="spark" />
        </svg>
      </div>
      <div v-if="selected.trades?.length" class="table-wrap">
        <div class="table-head">
          <span>成交明细</span>
          <button
            v-if="selected.trades.length > 40"
            type="button"
            class="linkish"
            @click="showAllTrades = !showAllTrades"
          >
            {{ showAllTrades ? '收起' : '显示全部' }}
          </button>
        </div>
        <table>
          <thead>
            <tr>
              <th>时间</th>
              <th>方向</th>
              <th>价格</th>
              <th>数量</th>
              <th>盈亏</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(t, i) in displayedTrades" :key="i">
              <td class="mono">{{ t.datetime }}</td>
              <td>{{ t.side || t.direction }}</td>
              <td>{{ Number(t.price).toFixed(2) }}</td>
              <td>{{ t.volume }}</td>
              <td>{{ t.pnl != null ? Number(t.pnl).toFixed(2) : '—' }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <div v-if="optimizeSummary?.best" class="compare">
      <h2>
        最优（{{ optimizeSummary.objective }}）
        <span class="muted">夏普 {{ optimizeSummary.best.sharpe_ratio?.toFixed(2) ?? '—' }}</span>
      </h2>
    </div>

    <div v-if="compare.length" class="compare">
      <h2>对比（{{ compare.length }}）</h2>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>标的</th>
              <th>状态</th>
              <th>收益%</th>
              <th>回撤%</th>
              <th>夏普</th>
              <th>成交</th>
              <th>参数</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="r in compare"
              :key="r.id"
              class="click"
              :class="{ on: optimizeSummary?.best?.id === r.id }"
              @click="emit('openRun', r.id)"
            >
              <td class="mono">{{ r.vt_symbol }}</td>
              <td>{{ r.status === 'failed' ? r.error_message || '失败' : '成功' }}</td>
              <td :class="{ up: (r.total_return || 0) > 0, down: (r.total_return || 0) < 0 }">
                {{ r.total_return != null ? r.total_return.toFixed(2) : '—' }}
              </td>
              <td>{{ r.max_drawdown != null ? r.max_drawdown.toFixed(2) : '—' }}</td>
              <td>{{ r.sharpe_ratio != null ? r.sharpe_ratio.toFixed(2) : '—' }}</td>
              <td>{{ r.trade_count ?? '—' }}</td>
              <td class="mono">
                {{
                  r.params?.fast_window != null
                    ? `${r.params.fast_window}/${r.params.slow_window}`
                    : '—'
                }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <p v-if="!selected && !compare.length" class="empty muted">
      {{ loading ? '加载中…' : '运行回测或从左侧打开历史记录' }}
    </p>
  </section>
</template>

<style scoped>
.right {
  border: 1px solid var(--border);
  border-radius: 0.75rem;
  background: var(--bg-elevated);
  padding: 12px;
  overflow: auto;
  display: grid;
  gap: 10px;
  align-content: start;
}
.linkish {
  background: transparent;
  border: none;
  color: var(--brand);
  text-align: left;
  padding: 0;
  cursor: pointer;
  font-size: 0.85rem;
}
.table-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 10px;
  border-bottom: 1px solid var(--border);
  font-size: 0.85rem;
  color: var(--muted);
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
.hint {
  margin: 0;
  line-height: 1.4;
}
.stats {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 8px;
}
.stat {
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 0.5rem;
  padding: 8px 10px;
}
.k {
  color: var(--muted);
  font-size: 0.75rem;
}
.v {
  font-size: 1.1rem;
  font-weight: 600;
  margin-top: 2px;
}
.chart {
  border: 1px solid var(--border);
  border-radius: 0.75rem;
  background: var(--bg);
  padding: 10px;
}
.chart svg {
  width: 100%;
  height: 140px;
  display: block;
}
.table-wrap {
  border: 1px solid var(--border);
  border-radius: 0.75rem;
  overflow: auto;
  background: var(--bg);
}
th,
td {
  padding: 8px 10px;
  border-bottom: 1px solid var(--border);
  font-size: 0.85rem;
  text-align: left;
  white-space: nowrap;
}
th {
  color: var(--muted);
  background: var(--surface-muted);
  font-weight: 500;
}
.click {
  cursor: pointer;
}
.mono {
  font-family: var(--mono);
}
.up {
  color: var(--danger);
}
.down {
  color: var(--ok);
}
.empty {
  text-align: center;
  padding: 40px;
}
h2 {
  margin: 0;
  font-size: 1.1rem;
}
.detail,
.compare {
  display: grid;
  gap: 12px;
}
@media (max-width: 900px) {
  .stats {
    grid-template-columns: 1fr 1fr;
  }
}
</style>

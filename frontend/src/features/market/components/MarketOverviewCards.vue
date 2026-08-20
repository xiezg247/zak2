<script setup lang="ts">
import { ref } from 'vue'
import { RouterLink } from 'vue-router'
import type { MarketOverview } from '../../../api/market'
import { fmtDateTime } from '../../../lib/format'

defineProps<{
  overview: MarketOverview
}>()

const emit = defineEmits<{
  'open-thresholds': []
}>()

const cycleInputsOpen = ref(false)

function posPct(cycle: NonNullable<MarketOverview['emotion_cycle']>): string {
  const lo = Math.round(cycle.position_pct_min * 100)
  const hi = Math.round(cycle.position_pct_max * 100)
  return `${lo}–${hi}%`
}
</script>

<template>
  <section class="cards">
    <div class="card">
      <div class="k">Redis</div>
      <div class="v status-line">
        <span class="dot" :class="overview.redis_available ? 'ok' : 'warn'"></span>
        {{ overview.redis_available ? '在线' : '离线' }} · {{ overview.quote_count }} 只
        <span class="trading-badge" :class="overview.is_trading ? 'on' : 'off'">
          {{ overview.is_trading ? '交易中' : '休市' }}
        </span>
      </div>
      <div class="s muted">{{ fmtDateTime(overview.updated_at) || '—' }}</div>
    </div>
    <div v-if="overview.emotion_cycle" class="card cycle-card">
      <div class="k">情绪周期</div>
      <div class="cycle-head">
        <div class="v">{{ overview.emotion_cycle.stage_label }}</div>
        <span
          class="cycle-gate"
          :class="overview.emotion_cycle.allow_new_positions ? 'ok' : 'warn'"
        >
          {{ overview.emotion_cycle.allow_new_positions ? '可新开' : '不宜新开' }}
        </span>
      </div>
      <div class="s muted">
        仓位建议 {{ posPct(overview.emotion_cycle) }}
        <template v-if="overview.emotion_cycle.allowed_mode_labels.length">
          · {{ overview.emotion_cycle.allowed_mode_labels.join('/') }}
        </template>
      </div>
      <div v-for="(w, i) in overview.emotion_cycle.warnings" :key="i" class="s warn">
        {{ w }}
      </div>
      <div class="cycle-actions">
        <button
          type="button"
          class="ghost tiny-btn"
          @click="cycleInputsOpen = !cycleInputsOpen"
        >
          {{ cycleInputsOpen ? '收起明细' : '明细' }}
        </button>
        <button type="button" class="ghost tiny-btn" @click="emit('open-thresholds')">
          阈值
        </button>
      </div>
      <div v-if="cycleInputsOpen && overview.emotion_cycle.inputs" class="s muted">
        涨停 {{ overview.emotion_cycle.inputs.limit_up_count ?? '—' }} · 跌停
        {{ overview.emotion_cycle.inputs.limit_down_count ?? '—' }} · 最高板
        {{ overview.emotion_cycle.inputs.max_limit_times ?? '—' }}
        <template v-if="overview.emotion_cycle.inputs.fear_greed_index != null">
          · 恐贪≈{{ overview.emotion_cycle.inputs.fear_greed_index }}
        </template>
        <template v-if="overview.emotion_cycle.inputs.index_above_ma5 === true">
          · 站上MA5</template
        >
        <template v-else-if="overview.emotion_cycle.inputs.index_above_ma5 === false">
          · 跌破MA5</template
        >
      </div>
    </div>
    <div v-else class="card">
      <div class="k">情绪周期</div>
      <div class="v muted">暂无数据</div>
      <p class="s muted empty-cycle-hint">
        可到 Ops 执行 warm_market_summary 预热。
        <RouterLink to="/ops" class="draft-link">去 Ops</RouterLink>
      </p>
    </div>
  </section>
</template>

<style scoped>
.cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 10px;
}
.card {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: 0.75rem;
  box-shadow: var(--shadow-card);
  padding: 14px 16px;
  display: grid;
  gap: 2px;
  align-content: start;
}
.card.cycle-card {
  position: relative;
  border-color: var(--brand-soft);
  background: linear-gradient(180deg, #fffdfb 0%, var(--surface) 100%);
}
.card.cycle-card::before {
  content: '';
  position: absolute;
  left: 0;
  top: 14px;
  bottom: 14px;
  width: 3px;
  border-radius: 999px;
  background: linear-gradient(180deg, var(--brand), #f5936a);
}
.k {
  color: var(--muted);
  font-size: 0.78rem;
  font-weight: 500;
  letter-spacing: 0.02em;
}
.v {
  margin-top: 4px;
  font-size: 1.1rem;
  font-weight: 600;
}
.status-line {
  display: flex;
  align-items: center;
  gap: 8px;
}
.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}
.dot.ok {
  background: var(--ok);
  box-shadow: 0 0 0 3px rgba(22, 163, 74, 0.15);
}
.dot.warn {
  background: var(--danger);
  box-shadow: 0 0 0 3px rgba(225, 29, 72, 0.15);
}
.trading-badge {
  margin-left: 2px;
  font-size: 0.72rem;
  font-weight: 600;
  padding: 1px 8px;
  border-radius: 999px;
  line-height: 1.5;
  white-space: nowrap;
}
.trading-badge.on {
  color: #fff;
  background: var(--ok);
}
.trading-badge.off {
  color: var(--ink-muted);
  background: var(--surface-muted);
  border: 1px solid var(--line-soft);
}
.s {
  margin-top: 4px;
  font-size: 0.8rem;
}
.cycle-head {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 8px;
  margin-top: 4px;
}
.cycle-head .v {
  margin-top: 0;
}
.cycle-gate {
  font-size: 0.8rem;
  font-weight: 600;
  padding: 3px 10px;
  border-radius: 999px;
  border: 1px solid var(--border);
}
.cycle-gate.ok {
  color: #fff;
  background: var(--ok);
  border-color: var(--ok);
}
.cycle-gate.warn {
  color: #fff;
  background: var(--danger);
  border-color: var(--danger);
}
.cycle-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 8px;
}
.ghost {
  border-radius: 0.5rem;
  padding: 6px 10px;
  border: 1px solid var(--border);
  cursor: pointer;
  background: transparent;
  color: var(--text);
}
.tiny-btn {
  padding: 2px 8px;
  font-size: 0.75rem;
}
.draft-link {
  color: var(--brand);
  margin-left: 4px;
}
.empty-cycle-hint {
  margin: 6px 0 0;
}
.warn {
  color: var(--danger);
}
.muted {
  color: var(--muted);
}
</style>

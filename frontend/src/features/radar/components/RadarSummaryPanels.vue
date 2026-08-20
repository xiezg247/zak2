<script setup lang="ts">
import { computed, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { fmtDateTime } from '../../../lib/format'
import type { RadarHorizon, RadarPredict } from '../../../api/market'

const props = defineProps<{
  horizon: RadarHorizon | null
  horizonErr: string
  predict: RadarPredict | null
  predictErr: string
  actingVt: string
}>()

const emit = defineEmits<{
  analyze: [vt: string, name?: string]
  addWatch: [vt: string, name?: string]
}>()

const horizonOpen = ref(false)
const predictOpen = ref(false)

function sealLabel(row: { seal_time_label?: string; first_time?: string }): string {
  const label = String(row.seal_time_label || '').trim()
  if (label) return label
  const ft = String(row.first_time || '').trim()
  if (ft.length >= 4) return `${ft.slice(0, 2)}:${ft.slice(2, 4)} 封板`
  return ''
}

const horizonHasCache = computed(() => Boolean(props.horizon?.computed_at))
const horizonHeadLabel = computed(() => {
  if (!horizonHasCache.value) return '暂无数据'
  const h = props.horizon!
  return (h.label || '').trim() || '启发式展望（基于共振）'
})
const horizonSummary = computed(() => {
  if (!horizonHasCache.value) return '暂无数据'
  const h = props.horizon!
  if (h.empty) return `扫描 ${h.scanned_total} · 无入选`
  return `入选 ${h.rows.length} · 扫描 ${h.scanned_total}`
})

const predictHasCache = computed(() => Boolean(props.predict?.computed_at))
const predictHeadLabel = computed(() => {
  if (!predictHasCache.value) return '暂无数据'
  const p = props.predict!
  return (p.label || '').trim() || '规则预测（共振+可解释加分）'
})
const predictSummary = computed(() => {
  if (!predictHasCache.value) return '暂无数据'
  const p = props.predict!
  if (p.empty) return `扫描 ${p.scanned_total} · 无入选`
  return `入选 ${p.rows.length} · 扫描 ${p.scanned_total}`
})
</script>

<template>
  <div class="summary-wrap">
    <div class="summary-bar">
      <button
        type="button"
        class="summary-card"
        :class="{ open: horizonOpen }"
        @click="horizonOpen = !horizonOpen"
      >
        <span class="summary-k">共振展望</span>
        <span class="summary-v muted">{{ horizonSummary }}</span>
        <span v-if="horizonHasCache && horizon?.computed_at" class="summary-t muted">
          {{ fmtDateTime(horizon.computed_at) }}
        </span>
        <span class="chevron">{{ horizonOpen ? '▴' : '▾' }}</span>
      </button>
      <button
        type="button"
        class="summary-card"
        :class="{ open: predictOpen }"
        @click="predictOpen = !predictOpen"
      >
        <span class="summary-k">规则预测</span>
        <span class="summary-v muted">{{ predictSummary }}</span>
        <span v-if="predictHasCache && predict?.computed_at" class="summary-t muted">
          {{ fmtDateTime(predict.computed_at) }}
        </span>
        <span class="chevron">{{ predictOpen ? '▴' : '▾' }}</span>
      </button>
    </div>

    <div v-if="horizonOpen" class="summary-panel">
      <div class="summary-panel-head">
        <strong>{{ horizonHeadLabel }}</strong>
        <span v-if="horizonHasCache && horizon?.computed_at" class="muted tiny">
          · {{ fmtDateTime(horizon.computed_at) }}
        </span>
      </div>
      <p v-if="horizonErr" class="horizon-err">{{ horizonErr }}</p>
      <template v-else-if="horizonHasCache">
        <p v-if="horizon?.empty" class="muted">
          上次扫描无达标共振标的（扫描 {{ horizon.scanned_total }} · 入选
          {{ horizon.refined_total }}）。
        </p>
        <div v-else-if="horizon?.rows.length" class="table-wrap horizon-table">
          <table>
            <thead>
              <tr>
                <th>#</th>
                <th>标的</th>
                <th>共振</th>
                <th>卡数</th>
                <th>细节</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(row, i) in horizon.rows" :key="row.vt_symbol">
                <td>{{ i + 1 }}</td>
                <td>
                  <span v-if="row.card_count >= 2" class="star">★</span>
                  {{ row.name || row.vt_symbol }}
                  <div class="mono muted tiny">{{ row.vt_symbol }}</div>
                </td>
                <td class="mono">{{ row.resonance_score.toFixed(1) }}</td>
                <td>{{ row.card_count }}</td>
                <td class="mono muted">
                  <template v-if="row.change_pct != null"
                    >涨幅 {{ row.change_pct.toFixed(2) }}%</template
                  >
                  <template v-if="row.last_price != null">
                    <template v-if="row.change_pct != null"> · </template>
                    现价 {{ row.last_price.toFixed(2) }}
                  </template>
                  <template v-if="row.card_titles.length">
                    <template v-if="row.change_pct != null || row.last_price != null"> · </template>
                    {{ row.card_titles.join(' / ') }}
                  </template>
                  <template v-if="sealLabel(row)">
                    <template
                      v-if="
                        row.change_pct != null || row.last_price != null || row.card_titles.length
                      "
                    >
                      ·
                    </template>
                    {{ sealLabel(row) }}
                  </template>
                  <template
                    v-if="
                      row.change_pct == null &&
                      row.last_price == null &&
                      !row.card_titles.length &&
                      !sealLabel(row)
                    "
                  >
                    —
                  </template>
                </td>
                <td class="ops">
                  <button
                    type="button"
                    class="ghost tiny-btn"
                    @click="emit('analyze', row.vt_symbol, row.name)"
                  >
                    析
                  </button>
                  <button
                    type="button"
                    class="ghost tiny-btn"
                    :disabled="!!actingVt"
                    @click="emit('addWatch', row.vt_symbol, row.name)"
                  >
                    自选
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </template>
      <template v-else>
        <p class="muted">
          暂无启发式展望数据。请于 Ops 手动执行
          <code class="mono">scan_horizon_outlook</code>（需先 warm_radar_card_snapshots）。
        </p>
        <RouterLink to="/ops" class="draft-link">去 Ops</RouterLink>
      </template>
    </div>

    <div v-if="predictOpen" class="summary-panel">
      <div class="summary-panel-head">
        <strong>{{ predictHeadLabel }}</strong>
        <span v-if="predictHasCache && predict?.computed_at" class="muted tiny">
          · {{ fmtDateTime(predict.computed_at) }}
        </span>
      </div>
      <p v-if="predictErr" class="horizon-err">{{ predictErr }}</p>
      <template v-else-if="predictHasCache">
        <p v-if="predict?.empty" class="muted">
          上次预测无入选行（候选 {{ predict.scanned_total }} · 缺日 K
          {{ predict.kline_missing }}）。
        </p>
        <div v-else-if="predict?.rows.length" class="table-wrap horizon-table">
          <table>
            <thead>
              <tr>
                <th>#</th>
                <th>标的</th>
                <th>预测分</th>
                <th>共振</th>
                <th>涨跌%</th>
                <th>封板</th>
                <th>理由</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(row, i) in predict.rows" :key="row.vt_symbol">
                <td>{{ i + 1 }}</td>
                <td>
                  {{ row.name || row.vt_symbol }}
                  <div class="mono muted tiny">{{ row.vt_symbol }}</div>
                </td>
                <td class="mono">{{ row.predict_score.toFixed(2) }}</td>
                <td class="mono">{{ row.resonance_score.toFixed(1) }}</td>
                <td class="mono">
                  {{ row.change_pct != null ? row.change_pct.toFixed(2) : '—' }}
                </td>
                <td class="muted tiny">{{ row.seal_time_label || '—' }}</td>
                <td class="muted tiny">{{ (row.reasons || []).join(' · ') || '—' }}</td>
                <td class="ops">
                  <button
                    type="button"
                    class="ghost tiny-btn"
                    @click="emit('analyze', row.vt_symbol, row.name)"
                  >
                    析
                  </button>
                  <button
                    type="button"
                    class="ghost tiny-btn"
                    :disabled="!!actingVt"
                    @click="emit('addWatch', row.vt_symbol, row.name)"
                  >
                    自选
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </template>
      <template v-else-if="horizonHasCache">
        <p class="muted">
          上次预测阶段失败或未写入，可于 Ops 重跑
          <code class="mono">scan_horizon_outlook</code>。
        </p>
        <RouterLink to="/ops" class="draft-link">去 Ops</RouterLink>
      </template>
      <template v-else>
        <p class="muted">
          暂无规则预测。请于 Ops 执行
          <code class="mono">scan_horizon_outlook</code>（与共振展望同 job）。
        </p>
        <RouterLink to="/ops" class="draft-link">去 Ops</RouterLink>
      </template>
    </div>
  </div>
</template>

<style scoped>
.summary-wrap {
  display: grid;
  gap: 12px;
}
.summary-bar {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 10px;
}
.summary-card {
  display: flex;
  align-items: center;
  gap: 8px;
  border: 1px solid var(--line);
  border-radius: 0.75rem;
  background: var(--surface);
  box-shadow: var(--shadow-card);
  padding: 8px 12px;
  cursor: pointer;
  text-align: left;
  transition:
    border-color 0.15s ease,
    background 0.15s ease;
}
.summary-card:hover {
  border-color: var(--brand-soft);
}
.summary-card.open {
  border-color: var(--brand-soft);
  background: var(--brand-light);
}
.summary-k {
  font-size: 0.85rem;
  font-weight: 600;
  white-space: nowrap;
}
.summary-v {
  font-size: 0.8rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.summary-t {
  font-size: 0.72rem;
  white-space: nowrap;
}
.chevron {
  margin-left: auto;
  color: var(--ink-faint);
  font-size: 0.7rem;
}
.summary-panel {
  border: 1px solid var(--line);
  border-radius: 0.75rem;
  background: var(--surface);
  box-shadow: var(--shadow-card);
  padding: 12px 16px;
}
.summary-panel-head {
  display: flex;
  align-items: baseline;
  gap: 8px;
  margin-bottom: 8px;
}
.summary-panel-head strong {
  font-size: 0.9rem;
  font-weight: 600;
}
.horizon-err {
  margin: 0;
  color: var(--danger);
  font-size: 0.85rem;
}
.horizon-table {
  margin-top: 8px;
}
.table-wrap {
  overflow: auto;
}
table {
  width: 100%;
  border-collapse: collapse;
}
th,
td {
  padding: 6px 8px;
  border-bottom: 1px solid var(--border);
  font-size: 0.85rem;
  text-align: left;
  white-space: nowrap;
}
.muted {
  color: var(--muted);
  font-size: 0.75rem;
}
.tiny {
  font-size: 0.72rem;
}
.mono {
  font-family: var(--mono);
}
.star {
  color: var(--brand);
}
.ops {
  display: flex;
  gap: 6px;
}
.ghost {
  background: var(--surface);
  border: 1px solid var(--line);
  color: var(--ink-muted);
  border-radius: 0.5rem;
  padding: 4px 8px;
  font-size: 0.75rem;
  cursor: pointer;
}
.ghost:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.tiny-btn {
  padding: 2px 8px;
  font-size: 0.75rem;
}
.draft-link {
  color: var(--brand);
  text-decoration: underline;
  font-size: 0.85rem;
}
</style>

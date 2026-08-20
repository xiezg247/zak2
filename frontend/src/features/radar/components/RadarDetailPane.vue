<script setup lang="ts">
import type { RadarCard } from '../../../api/market'

const props = defineProps<{
  active: RadarCard | null
  detailMsg: string
  actingVt: string
  cardCountByVt: Map<string, number>
}>()

const emit = defineEmits<{
  addWatch: [vt: string, name?: string]
  openWatchlist: [vt: string]
  openNotes: [vt: string]
}>()

const SOURCE_LABELS: Record<string, string> = {
  cache: '缓存',
  synthesized: '合成',
}

function sourceLabel(source: string): string {
  return SOURCE_LABELS[source] || source
}

function rowLabel(row: Record<string, unknown>) {
  return String(row.name || row.vt_symbol || row.tf_symbol || row.sector_id || '—')
}

function sealLabel(
  row: Record<string, unknown> | { seal_time_label?: string; first_time?: string },
) {
  const label = String(row.seal_time_label || '').trim()
  if (label) return label
  const ft = String((row as { first_time?: string }).first_time || '').trim()
  if (ft.length >= 4) return `${ft.slice(0, 2)}:${ft.slice(2, 4)} 封板`
  return ''
}

function rowVt(row: Record<string, unknown>): string {
  for (const k of ['vt_symbol', 'tf_symbol', 'symbol'] as const) {
    const v = String(row[k] || '').trim()
    if (v) return v
  }
  return ''
}

function rowVtKeys(row: Record<string, unknown>): string[] {
  const keys: string[] = []
  for (const k of ['vt_symbol', 'tf_symbol', 'symbol'] as const) {
    const v = String(row[k] || '').trim()
    if (v) keys.push(v)
  }
  return keys
}

function rowResonanceCount(row: Record<string, unknown>): number {
  for (const k of rowVtKeys(row)) {
    const n = props.cardCountByVt.get(k)
    if (typeof n === 'number') return n
  }
  return 0
}
</script>

<template>
  <section class="detail-pane">
    <template v-if="active">
      <div class="pane-head">
        <h2>{{ active.title }}</h2>
        <span class="muted tiny"
          >{{ active.rows.length }} 行 · {{ sourceLabel(active.source) }}</span
        >
      </div>
      <p v-if="active.subtitle || active.empty_message" class="muted pane-sub">
        {{ active.subtitle }} {{ active.empty_message }}
      </p>
      <p v-if="detailMsg" class="detail-msg">{{ detailMsg }}</p>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>#</th>
              <th>标的</th>
              <th>细节</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(row, i) in active.rows" :key="i">
              <td>{{ i + 1 }}</td>
              <td>
                <span v-if="rowResonanceCount(row) >= 2" class="star">★</span>
                {{ rowLabel(row) }}
              </td>
              <td class="mono muted">
                <template v-if="row.leader_tier">
                  {{ row.leader_tier }} · 评分 {{ Number(row.leader_score || 0).toFixed(0) }}
                  <template v-if="row.limit_times != null"> · {{ row.limit_times }}板</template>
                  <template v-if="sealLabel(row)"> · {{ sealLabel(row) }}</template>
                </template>
                <template v-else-if="row.change_pct != null"
                  >涨幅 {{ Number(row.change_pct).toFixed(2) }}%</template
                >
                <template v-else-if="row.net_flow_yi != null"
                  >净流入 {{ Number(row.net_flow_yi).toFixed(2) }} 亿</template
                >
                <template v-else-if="row.limit_times != null">
                  {{ row.limit_times }} 板
                  <template v-if="sealLabel(row)"> · {{ sealLabel(row) }}</template>
                </template>
                <template v-else-if="row.role">{{ row.role }}</template>
                <template v-else-if="sealLabel(row)">{{ sealLabel(row) }}</template>
                <template v-else>—</template>
              </td>
              <td class="row-actions">
                <template v-if="rowVt(row)">
                  <button
                    type="button"
                    class="tiny-btn"
                    :disabled="actingVt === rowVt(row)"
                    @click="emit('addWatch', rowVt(row), String(row.name || ''))"
                  >
                    加自选
                  </button>
                  <button
                    type="button"
                    class="tiny-btn"
                    @click="emit('openWatchlist', rowVt(row))"
                  >
                    在自选打开
                  </button>
                  <button type="button" class="tiny-btn" @click="emit('openNotes', rowVt(row))">
                    去笔记
                  </button>
                </template>
                <template v-else>—</template>
              </td>
            </tr>
            <tr v-if="!active.rows.length">
              <td colspan="4" class="empty">{{ active.empty_message || '暂无行' }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>
    <div v-else class="empty-pane">
      <p class="muted">选择一张卡片查看详情</p>
    </div>
  </section>
</template>

<style scoped>
.detail-pane {
  grid-area: detail;
  display: grid;
  gap: 8px;
  align-content: start;
  padding: 14px 16px;
  border: 1px solid var(--line);
  border-radius: 0.75rem;
  background: var(--surface);
  box-shadow: var(--shadow-card);
}
.pane-head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 10px;
}
.pane-head h2 {
  margin: 0;
  font-size: 1rem;
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.pane-sub {
  margin: 0;
}
.detail-msg {
  margin: 0;
  font-size: 0.85rem;
  color: var(--muted);
}
.empty-pane {
  display: grid;
  place-items: center;
  padding: 32px 8px;
  color: var(--ink-faint);
  font-size: 0.9rem;
}
.empty-pane p {
  margin: 0;
}
.row-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  white-space: nowrap;
}
.table-wrap {
  border: 1px solid var(--line);
  border-radius: 0.75rem;
  overflow: auto;
  background: var(--surface);
  box-shadow: var(--shadow-card);
}
th,
td {
  padding: 8px 10px;
  border-bottom: 1px solid var(--line);
  font-size: 0.85rem;
  text-align: left;
  white-space: nowrap;
}
th {
  color: var(--ink-muted);
  background: var(--surface-muted);
  position: sticky;
  top: 0;
  font-weight: 500;
  z-index: 1;
}
tbody tr:hover td {
  background: var(--surface-muted);
}
.detail-pane .table-wrap tbody tr:hover td {
  background: var(--brand-light);
}
.mono {
  font-family: var(--mono);
}
.muted {
  color: var(--muted);
  font-size: 0.85rem;
}
.tiny {
  font-size: 0.72rem;
}
.empty {
  text-align: center;
  color: var(--muted);
  padding: 24px !important;
}
.star {
  color: var(--brand);
  margin-right: 2px;
}
.tiny-btn {
  background: var(--surface);
  border: 1px solid var(--line);
  color: var(--ink-muted);
  border-radius: 0.5rem;
  padding: 2px 8px;
  font-size: 0.75rem;
  cursor: pointer;
  transition:
    background 0.15s ease,
    color 0.15s ease,
    border-color 0.15s ease;
}
.tiny-btn:hover:not(:disabled) {
  background: var(--brand-light);
  color: var(--brand);
  border-color: var(--brand-soft);
}
.tiny-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>

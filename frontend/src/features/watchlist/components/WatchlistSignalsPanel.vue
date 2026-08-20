<script setup lang="ts">
import { formatPrice } from '../../../lib/format'
import type { StrategySignalRow } from '../../../api/watchlist'

defineProps<{
  signals: StrategySignalRow[]
  panelSymbols: string[]
  panelMax: number
  signalAdd: string
  activeSignalVt: string
  signalError: string
  signalMsg: string
}>()

const emit = defineEmits<{
  'update:signalAdd': [value: string]
  add: [vt?: string]
  remove: [vt: string]
  select: [vt: string]
  pick: [vt: string]
  analyze: [vt: string, name: string]
}>()

function signalClass(sig: string) {
  if (sig === 'buy') return 'up'
  if (sig === 'sell') return 'down'
  return ''
}
</script>

<template>
  <section class="card">
    <h3>
      信号区
      <span class="muted">{{ signals.length }}</span>
      <span class="muted"> · 名单 {{ panelSymbols.length }}/{{ panelMax }}</span>
    </h3>
    <div class="pos-form signal-form">
      <div class="row">
        <input
          :value="signalAdd"
          placeholder="加入信号名单：600519.SSE"
          @input="emit('update:signalAdd', ($event.target as HTMLInputElement).value)"
          @keyup.enter="emit('add')"
        />
        <button type="button" class="ghost" @click="emit('add', activeSignalVt)">用选中</button>
        <button type="button" class="primary" @click="emit('add')">加入</button>
      </div>
      <div v-if="panelSymbols.length" class="chips">
        <span v-for="vt in panelSymbols" :key="vt" class="chip-tag">
          <button type="button" class="chip-link" @click="emit('select', vt)">{{ vt }}</button>
          <button type="button" class="link" @click="emit('remove', vt)">×</button>
        </span>
      </div>
      <p v-else class="muted tip">名单为空时回退「自选实时计算」；上限 {{ panelMax }} 只。</p>
      <p v-if="signalError" class="err">{{ signalError }}</p>
      <p v-else-if="signalMsg" class="muted">{{ signalMsg }}</p>
    </div>
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>代码</th>
            <th>名称</th>
            <th>现价</th>
            <th>信号</th>
            <th>强度</th>
            <th>摘要</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="row in signals"
            :key="row.vt_symbol"
            :class="{ on: activeSignalVt === row.vt_symbol }"
            @click="emit('pick', row.vt_symbol)"
          >
            <td class="mono">{{ row.vt_symbol }}</td>
            <td>{{ row.name || '—' }}</td>
            <td>{{ formatPrice(row.last_price) }}</td>
            <td :class="signalClass(row.signal)">{{ row.signal_label }}</td>
            <td>
              <template v-if="row.strength_tier_label">
                {{ row.strength_tier_label
                }}<span v-if="row.strength != null"> · {{ row.strength.toFixed(1) }}</span>
              </template>
              <template v-else>
                {{ row.strength != null ? row.strength.toFixed(0) : '—' }}
              </template>
            </td>
            <td class="clip">{{ row.reason_summary || '—' }}</td>
            <td>
              <button
                type="button"
                class="link"
                @click.stop="emit('analyze', row.vt_symbol, row.name)"
              >
                析
              </button>
              <button
                v-if="panelSymbols.includes(row.vt_symbol)"
                type="button"
                class="link"
                @click.stop="emit('remove', row.vt_symbol)"
              >
                移出
              </button>
              <button
                v-else
                type="button"
                class="link"
                @click.stop="emit('add', row.vt_symbol)"
              >
                入名单
              </button>
            </td>
          </tr>
          <tr v-if="!signals.length">
            <td colspan="7" class="empty">无信号（可先编辑名单，或确认日 K 已补全）</td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>

<style scoped>
.card {
  border: 1px solid var(--line);
  border-radius: 0.75rem;
  background: var(--surface);
  box-shadow: var(--shadow-card);
  padding: 14px 16px;
}
.card h3 {
  margin: 0 0 10px;
  font-size: 0.9rem;
  font-weight: 600;
}
.pos-form {
  display: grid;
  gap: 8px;
  margin-bottom: 10px;
  padding: 10px;
  border: 1px solid var(--border);
  border-radius: 0.75rem;
  background: var(--surface-muted);
}
.signal-form .row {
  grid-template-columns: 1fr auto auto;
}
.row {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 8px;
}
.chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.chip-tag {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  border: 1px solid var(--border);
  border-radius: 0.5rem;
  padding: 2px 6px;
  font-size: 0.8rem;
  background: var(--bg);
}
.chip-link {
  background: none;
  border: none;
  color: var(--text);
  font-family: var(--mono);
  padding: 0;
  cursor: pointer;
}
.chip-link:hover {
  color: var(--brand);
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
.clip {
  max-width: 220px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.tip {
  margin: 0;
  font-size: 0.75rem;
}
.table-wrap {
  overflow: auto;
}
table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.875rem;
}
th,
td {
  padding: 8px 10px;
  border-bottom: 1px solid var(--line-soft);
  text-align: left;
}
th {
  color: var(--ink-muted);
  font-weight: 500;
  background: var(--surface-muted);
}
tbody tr {
  cursor: pointer;
}
tbody tr:hover td {
  background: var(--brand-light);
}
tbody tr.on td {
  background: var(--brand-light);
}
.empty {
  text-align: center;
  color: var(--ink-faint);
  padding: 24px !important;
}
.mono {
  font-variant-numeric: tabular-nums;
  font-family: var(--mono, ui-monospace, monospace);
}
.up {
  color: var(--up, #c62828);
}
.down {
  color: var(--down, #2e7d32);
}
</style>

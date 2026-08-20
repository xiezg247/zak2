<script setup lang="ts">
import { computed } from 'vue'
import { formatAmountYi, formatNum2, formatPrice } from '../../../lib/format'
import type { WatchlistItem } from '../../../api/watchlist'

type SortKey = 'last_price' | 'change_pct' | 'turnover_rate' | 'amount' | null
type OptionalCol = 'industry' | 'turnover_rate' | 'amount'

const props = defineProps<{
  rows: WatchlistItem[]
  totalCount: number
  colVisible: Record<OptionalCol, boolean>
  checkedVts: string[]
  allDisplayedChecked: boolean
  sortKey: SortKey
  sortDir: 'asc' | 'desc'
  tableColspan: number
}>()

const emit = defineEmits<{
  'toggle-sort': [key: Exclude<SortKey, null>]
  'toggle-checked': [vt: string]
  'toggle-all': []
  chart: [item: WatchlistItem]
  fund: [item: WatchlistItem]
  analyze: [item: WatchlistItem]
  remove: [item: WatchlistItem]
}>()

const checkedSet = computed(() => new Set(props.checkedVts))

function sortMark(key: Exclude<SortKey, null>): string {
  if (props.sortKey !== key) return ''
  return props.sortDir === 'asc' ? ' ▲' : ' ▼'
}
</script>

<template>
  <div class="table-wrap">
    <table>
      <thead>
        <tr>
          <th class="check-col">
            <input
              type="checkbox"
              :checked="allDisplayedChecked"
              :disabled="!rows.length"
              @change="emit('toggle-all')"
            />
          </th>
          <th>#</th>
          <th>代码</th>
          <th>名称</th>
          <th v-if="colVisible.industry">行业</th>
          <th class="sortable" @click="emit('toggle-sort', 'last_price')">
            现价{{ sortMark('last_price') }}
          </th>
          <th class="sortable" @click="emit('toggle-sort', 'change_pct')">
            涨幅%{{ sortMark('change_pct') }}
          </th>
          <th
            v-if="colVisible.turnover_rate"
            class="sortable"
            @click="emit('toggle-sort', 'turnover_rate')"
          >
            换手%{{ sortMark('turnover_rate') }}
          </th>
          <th v-if="colVisible.amount" class="sortable" @click="emit('toggle-sort', 'amount')">
            成交额{{ sortMark('amount') }}
          </th>
          <th class="ops">操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="(item, idx) in rows" :key="item.vt_symbol">
          <td class="check-col" @click.stop>
            <input
              type="checkbox"
              :checked="checkedSet.has(item.vt_symbol)"
              @change="emit('toggle-checked', item.vt_symbol)"
            />
          </td>
          <td>
            <span class="rank-badge">{{ idx + 1 }}</span>
          </td>
          <td class="mono">{{ item.vt_symbol }}</td>
          <td>
            {{ item.name || '—' }}
            <span v-if="item.suspended" class="suspend-tag" title="停牌">停</span>
          </td>
          <td v-if="colVisible.industry">
            {{ item.industry?.trim() ? item.industry : '—' }}
          </td>
          <td>{{ formatPrice(item.last_price) }}</td>
          <td
            :class="{
              up: (item.change_pct || 0) > 0,
              down: (item.change_pct || 0) < 0,
            }"
          >
            {{ formatNum2(item.change_pct) }}
          </td>
          <td v-if="colVisible.turnover_rate">{{ formatNum2(item.turnover_rate) }}</td>
          <td v-if="colVisible.amount">{{ formatAmountYi(item.amount) }}</td>
          <td class="ops">
            <div class="row-ops">
              <button type="button" class="icon-btn" title="K线" @click="emit('chart', item)">
                <svg
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="1.6"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                >
                  <path
                    d="M5 4v2.5M5 17.5V20M5 6.5a1.5 1.5 0 011.5-1.5h0A1.5 1.5 0 018 6.5v11a1.5 1.5 0 01-1.5 1.5h0A1.5 1.5 0 015 17.5v-11z"
                  />
                  <path
                    d="M12 2v4M12 18v4M12 6a1.5 1.5 0 011.5-1.5h0A1.5 1.5 0 0115 6v12a1.5 1.5 0 01-1.5 1.5h0A1.5 1.5 0 0112 18V6z"
                  />
                  <path
                    d="M19 6v3M19 17v4M19 9a1.5 1.5 0 011.5-1.5h0a1.5 1.5 0 011.5 1.5v8a1.5 1.5 0 01-1.5 1.5h0a1.5 1.5 0 01-1.5-1.5V9z"
                  />
                </svg>
              </button>
              <button type="button" class="icon-btn" title="基本面" @click="emit('fund', item)">
                <svg
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="1.6"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                >
                  <path d="M3 3h18v18H3V3zM7 7h10M7 11h10M7 15h6" />
                </svg>
              </button>
              <button
                type="button"
                class="icon-btn"
                title="分析"
                @click.stop="emit('analyze', item)"
              >
                <svg
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="1.6"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                >
                  <path
                    d="M8.25 21v-4.875c0-.621.504-1.125 1.125-1.125h5.25c.621 0 1.125.504 1.125 1.125V21m0 0h4.5M3.75 21h4.5M3.75 21V9m0 0l-1.5 3M3.75 9l9-6 9 6m-13.5 0v6h4.5v-6"
                  />
                </svg>
              </button>
              <button
                type="button"
                class="icon-btn danger"
                title="删除"
                @click="emit('remove', item)"
              >
                <svg
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  stroke-width="1.6"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                >
                  <path
                    d="M3 6h18M8 6V4a1 1 0 011-1h6a1 1 0 011 1v2m3 0v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6h14zM10 11v6M14 11v6"
                  />
                </svg>
              </button>
            </div>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="tableColspan" class="empty">
            {{ totalCount === 0 ? '暂无自选标的，上方输入代码添加' : '无匹配标的' }}
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<style scoped>
.check-col {
  width: 32px;
  text-align: center;
  padding-left: 8px;
  padding-right: 4px;
}
.check-col input[type='checkbox'] {
  cursor: pointer;
}
.table-wrap {
  border: 1px solid var(--line);
  border-radius: 0.75rem;
  background: var(--surface);
  box-shadow: var(--shadow-card);
  overflow: auto;
  max-height: 70vh;
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
  position: sticky;
  top: 0;
  font-weight: 500;
}
th.sortable {
  cursor: pointer;
  user-select: none;
}
th.sortable:hover {
  color: var(--text);
}
tbody tr:hover td {
  background: var(--surface-muted);
}
.rank-badge {
  display: inline-grid;
  place-items: center;
  min-width: 24px;
  height: 20px;
  border-radius: 999px;
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--ink-muted);
  background: var(--surface-muted);
  font-variant-numeric: tabular-nums;
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
.icon-btn.danger:hover {
  border-color: var(--danger);
  color: var(--danger);
}
.icon-btn svg {
  width: 15px;
  height: 15px;
}
.row-ops {
  display: flex;
  gap: 4px;
}
th.ops,
td.ops {
  text-align: right;
}
.suspend-tag {
  margin-left: 4px;
  font-size: 0.7rem;
  padding: 0 4px;
  border-radius: 0.25rem;
  border: 1px solid var(--border);
  color: var(--danger, #b42318);
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
  color: var(--muted);
  padding: 28px !important;
}
</style>

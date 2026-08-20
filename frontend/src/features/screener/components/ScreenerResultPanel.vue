<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { cmpNullable } from '../../../lib/sort'
import type { RunDetail } from '../../../api/screener'

const props = defineProps<{
  current: RunDetail | null
  statusText: string
  error: string
  isRadarLeader: boolean
  batchBusy: boolean
}>()

const emit = defineEmits<{
  exportCsv: []
  addSelected: [rows: Record<string, unknown>[]]
  addWatchlist: [row: Record<string, unknown>]
  findPeers: [row: Record<string, unknown>]
}>()

const rows = computed(() => props.current?.result?.rows || [])

type ResultSortKey = 'last_price' | 'change_pct' | 'turnover_rate' | 'volume_ratio' | 'score' | null

const resultFilter = ref('')
const sortKey = ref<ResultSortKey>(null)
const sortDir = ref<'asc' | 'desc'>('desc')
const showDiffDetail = ref(false)
const selectedVts = ref<Record<string, true>>({})

function rowNum(row: Record<string, unknown>, key: string): number | null {
  const v = Number(row[key])
  return Number.isFinite(v) ? v : null
}

function rowScore(row: Record<string, unknown>): number | null {
  for (const k of ['similarity_score', 'pattern_score', 'leader_score', 'score'] as const) {
    const v = rowNum(row, k)
    if (v != null) return v
  }
  return null
}

function toggleSort(key: Exclude<ResultSortKey, null>) {
  if (sortKey.value === key) {
    sortDir.value = sortDir.value === 'asc' ? 'desc' : 'asc'
  } else {
    sortKey.value = key
    sortDir.value = 'desc'
  }
}

function clearSort() {
  sortKey.value = null
}

function toggleColSort(key: string) {
  toggleSort(key as Exclude<ResultSortKey, null>)
}

function colSortMark(key: string): string {
  return sortMark(key as Exclude<ResultSortKey, null>)
}

function sortMark(key: Exclude<ResultSortKey, null>): string {
  if (sortKey.value !== key) return ''
  return sortDir.value === 'asc' ? ' ▲' : ' ▼'
}

function sortValue(row: Record<string, unknown>, key: Exclude<ResultSortKey, null>): number | null {
  if (key === 'score') return rowScore(row)
  return rowNum(row, key)
}

const displayedRows = computed(() => {
  const q = resultFilter.value.trim().toLowerCase()
  let list = rows.value as Record<string, unknown>[]
  if (q) {
    list = list.filter((row) => {
      const vt = String(row.vt_symbol || row.symbol || '').toLowerCase()
      const name = String(row.name || '').toLowerCase()
      const ind = String(row.industry || '').toLowerCase()
      return vt.includes(q) || name.includes(q) || ind.includes(q)
    })
  }
  const key = sortKey.value
  if (!key) return list
  const dir = sortDir.value
  return [...list].sort((a, b) => cmpNullable(sortValue(a, key), sortValue(b, key), dir))
})

type ColGroup = {
  label: string
  cls?: string
  cols: { key: string; label: string; sortable?: boolean; hint?: boolean }[]
}

const COL_GROUPS: ColGroup[] = [
  {
    label: '标的',
    cols: [
      { key: 'symbol', label: '代码' },
      { key: 'name', label: '名称' },
      { key: 'industry', label: '行业' },
    ],
  },
  {
    label: '行情',
    cls: 'g-quote',
    cols: [
      { key: 'last_price', label: '现价', sortable: true },
      { key: 'change_pct', label: '涨幅%', sortable: true },
      { key: 'turnover_rate', label: '换手%', sortable: true },
      { key: 'volume_ratio', label: '量比', sortable: true },
    ],
  },
  {
    label: '盘口',
    cls: 'g-tape',
    cols: [
      { key: 'limit_times', label: '连板' },
      { key: 'leader_tier', label: '分层' },
    ],
  },
  {
    label: '基本面',
    cls: 'g-fund',
    cols: [
      { key: 'pe_ttm', label: 'PE' },
      { key: 'total_mv_yi', label: '市值亿' },
    ],
  },
  {
    label: '资金',
    cls: 'g-flow',
    cols: [{ key: 'net_mf_wan', label: '净流入万' }],
  },
  {
    label: '评分',
    cls: 'g-score',
    cols: [
      { key: 'score', label: '得分', sortable: true },
      { key: 'pattern_hint', label: '形态说明', hint: true },
    ],
  },
]

const flatCols = COL_GROUPS.flatMap((g) => g.cols)

function rowVt(row: Record<string, unknown>): string {
  return String(row.vt_symbol || row.symbol || '').trim()
}

function clearSelected() {
  selectedVts.value = {}
}

function isSelected(vt: string): boolean {
  return !!selectedVts.value[vt]
}

function toggleVt(vt: string) {
  if (!vt) return
  const next = { ...selectedVts.value }
  if (next[vt]) delete next[vt]
  else next[vt] = true
  selectedVts.value = next
}

const selectedCount = computed(() => Object.keys(selectedVts.value).length)

const allDisplayedSelected = computed(() => {
  const list = displayedRows.value as Record<string, unknown>[]
  if (!list.length) return false
  return list.every((row) => {
    const vt = rowVt(row)
    return vt && isSelected(vt)
  })
})

function toggleSelectAllDisplayed() {
  const list = displayedRows.value as Record<string, unknown>[]
  if (allDisplayedSelected.value) {
    const next = { ...selectedVts.value }
    for (const row of list) {
      const vt = rowVt(row)
      if (vt) delete next[vt]
    }
    selectedVts.value = next
    return
  }
  const next = { ...selectedVts.value }
  for (const row of list) {
    const vt = rowVt(row)
    if (vt) next[vt] = true
  }
  selectedVts.value = next
}

function pruneSelectedToDisplayed() {
  const allow = new Set(
    (displayedRows.value as Record<string, unknown>[]).map(rowVt).filter(Boolean),
  )
  const next: Record<string, true> = {}
  for (const vt of Object.keys(selectedVts.value)) {
    if (allow.has(vt)) next[vt] = true
  }
  selectedVts.value = next
}

watch(displayedRows, () => pruneSelectedToDisplayed())

watch(
  () => props.current?.id,
  () => {
    resultFilter.value = ''
    clearSelected()
    showDiffDetail.value = false
    clearSort()
  },
)

const industry = computed(() => props.current?.result?.industry_dist || [])
const diff = computed(() => props.current?.result?.diff)

function rowSealLabel(row: Record<string, unknown>): string {
  const label = String(row.seal_time_label || '').trim()
  if (label) return label
  const ft = String(row.first_time || '').trim()
  if (ft.length >= 4) return `${ft.slice(0, 2)}:${ft.slice(2, 4)} 封板`
  return ''
}

function applyDiffFilter(vt: string) {
  resultFilter.value = vt
}

function toggleDiffDetail() {
  showDiffDetail.value = !showDiffDetail.value
}

function onAddSelected() {
  const list = displayedRows.value as Record<string, unknown>[]
  const queue = list.filter((row) => {
    const vt = rowVt(row)
    return vt && isSelected(vt)
  })
  if (!queue.length) return
  emit('addSelected', queue)
}
</script>

<template>
  <div class="result-panel">
    <div class="run-status">
      <p v-if="statusText" class="status">{{ statusText }}</p>
      <p v-if="error" class="err">{{ error }}</p>
      <p v-if="!statusText && !error" class="hint muted">
        配置左侧参数后运行；点击表格行「自选 / 找同类」快速操作
      </p>
    </div>

    <div v-if="current" class="toolbar">
      <strong>{{ current.condition }}</strong>
      <span class="muted">扫描 {{ current.total_scanned }} · 命中 {{ current.row_count }}</span>
      <span class="spacer"></span>
      <button type="button" class="ghost" @click="emit('exportCsv')">导出 CSV</button>
      <button
        type="button"
        class="ghost"
        :disabled="batchBusy || selectedCount === 0"
        @click="onAddSelected"
      >
        {{ batchBusy ? '加入中…' : `加入自选 (${selectedCount})` }}
      </button>
    </div>
    <div v-if="current" class="row filter-row">
      <input v-model="resultFilter" placeholder="过滤代码/名称/行业" />
      <button v-if="sortKey" type="button" class="ghost" @click="clearSort">默认序</button>
    </div>

    <div v-if="diff" class="diff">
      <div class="diff-summary">
        <span class="chip">新增 {{ diff.added.length }}</span>
        <span class="chip">移除 {{ diff.removed.length }}</span>
        <span class="chip">保留 {{ diff.kept.length }}</span>
        <button type="button" class="link" @click="toggleDiffDetail">
          {{ showDiffDetail ? '收起' : '详情' }}
        </button>
      </div>
      <div v-if="showDiffDetail" class="diff-detail">
        <div v-if="diff.added.length" class="diff-group">
          <strong>新增</strong>
          <div class="chips">
            <button
              v-for="vt in diff.added"
              :key="'a-' + vt"
              type="button"
              class="chip-link mono"
              @click="applyDiffFilter(vt)"
            >
              {{ vt }}
            </button>
          </div>
        </div>
        <div v-if="diff.removed.length" class="diff-group">
          <strong>移除</strong>
          <div class="chips">
            <button
              v-for="vt in diff.removed"
              :key="'r-' + vt"
              type="button"
              class="chip-link mono"
              @click="applyDiffFilter(vt)"
            >
              {{ vt }}
            </button>
          </div>
        </div>
        <p v-if="!diff.added.length && !diff.removed.length" class="muted tip">无新增或移除</p>
      </div>
    </div>

    <div class="table-wrap">
      <table>
        <thead>
          <tr class="group-row">
            <th class="sel-col" colspan="2"></th>
            <th v-for="g in COL_GROUPS" :key="g.label" :class="g.cls" :colspan="g.cols.length">
              {{ g.label }}
            </th>
            <th class="ops-col"></th>
          </tr>
          <tr class="col-row">
            <th class="sel-col">
              <input
                type="checkbox"
                :checked="allDisplayedSelected"
                :disabled="!displayedRows.length"
                @change="toggleSelectAllDisplayed"
              />
            </th>
            <th class="sel-col">#</th>
            <template v-for="c in flatCols" :key="c.key">
              <th v-if="c.sortable" class="sortable" @click="toggleColSort(c.key)">
                {{ c.label }}{{ colSortMark(c.key) }}
              </th>
              <th v-else :class="{ 'hint-cell': c.hint }">{{ c.label }}</th>
            </template>
            <th class="ops-col"></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(row, i) in displayedRows" :key="String(row.symbol)">
            <td class="sel-col" @click.stop>
              <input
                type="checkbox"
                :checked="isSelected(rowVt(row))"
                @change="toggleVt(rowVt(row))"
              />
            </td>
            <td class="sel-col">{{ i + 1 }}</td>
            <td class="mono">{{ row.vt_symbol || row.symbol }}</td>
            <td>{{ row.name }}</td>
            <td>{{ String(row.industry || '').trim() || '—' }}</td>
            <td class="g-quote">{{ Number(row.last_price || 0).toFixed(2) }}</td>
            <td
              class="g-quote"
              :class="{ up: Number(row.change_pct) > 0, down: Number(row.change_pct) < 0 }"
            >
              {{ Number(row.change_pct || 0).toFixed(2) }}
            </td>
            <td class="g-quote">{{ Number(row.turnover_rate || 0).toFixed(2) }}</td>
            <td class="g-quote">{{ Number(row.volume_ratio || 0).toFixed(2) }}</td>
            <td class="g-tape">
              {{ row.limit_times != null ? Number(row.limit_times).toFixed(0) : '—' }}
              <span v-if="rowSealLabel(row)" class="muted seal-tag">
                · {{ rowSealLabel(row) }}</span
              >
            </td>
            <td class="g-tape">{{ row.leader_tier_label || row.leader_tier || '—' }}</td>
            <td class="g-fund">
              {{ row.pe_ttm != null ? Number(row.pe_ttm).toFixed(2) : '—' }}
            </td>
            <td class="g-fund">
              {{
                row.total_mv_yi != null
                  ? Number(row.total_mv_yi).toFixed(1)
                  : row.total_mv
                    ? (Number(row.total_mv) / 10000).toFixed(1)
                    : '—'
              }}
            </td>
            <td class="g-flow">
              {{
                row.net_mf_wan != null
                  ? Number(row.net_mf_wan).toFixed(0)
                  : row.net_mf_amount
                    ? Number(row.net_mf_amount).toFixed(0)
                    : '—'
              }}
            </td>
            <td class="g-score">
              {{
                row.similarity_score != null
                  ? Number(row.similarity_score).toFixed(1)
                  : row.pattern_score != null
                    ? Number(row.pattern_score).toFixed(1)
                    : row.leader_score != null
                      ? Number(row.leader_score).toFixed(1)
                      : row.score != null
                        ? Number(row.score).toFixed(3)
                        : '—'
              }}
            </td>
            <td
              class="g-score hint-cell"
              :title="
                [
                  row.pattern_hint || row.hit_reason || '',
                  isRadarLeader ? rowSealLabel(row) : '',
                ]
                  .filter(Boolean)
                  .join(' · ') || ''
              "
            >
              <template v-if="row.pattern_hint || row.hit_reason">
                {{ row.pattern_hint || row.hit_reason }}
              </template>
              <template v-else-if="isRadarLeader && rowSealLabel(row)">{{
                rowSealLabel(row)
              }}</template>
              <template v-else>—</template>
            </td>
            <td class="ops-col row-actions">
              <button type="button" class="link" @click="emit('addWatchlist', row)">自选</button>
              <button type="button" class="link" @click="emit('findPeers', row)">找同类</button>
            </td>
          </tr>
          <tr v-if="!displayedRows.length">
            <td :colspan="flatCols.length + 3" class="empty">
              {{ rows.length === 0 ? '运行选股后在此显示结果' : '无匹配结果' }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div v-if="industry.length" class="industry">
      <h3>行业分布</h3>
      <div class="chips">
        <span v-for="item in industry.slice(0, 12)" :key="item.industry" class="chip">
          {{ item.industry }} {{ item.count }}
        </span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.result-panel {
  display: grid;
  gap: 12px;
  align-content: start;
}
.run-status {
  min-height: 20px;
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  padding: 8px 12px;
  border: 1px solid var(--line);
  border-radius: 0.75rem;
  background: var(--surface);
  box-shadow: var(--shadow-card);
}
.run-status p {
  margin: 0;
}
.row {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 8px;
}
.filter-row {
  grid-template-columns: 1fr auto;
}
input {
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: 0.5rem;
  color: var(--text);
  padding: 8px 10px;
}
.hint {
  margin: 0;
  font-size: 0.75rem;
  line-height: 1.4;
}
.hint-cell {
  max-width: 180px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 0.78rem;
  color: var(--muted);
}
.seal-tag {
  font-size: 0.75rem;
}
.ghost {
  background: transparent;
  border: 1px solid var(--border);
  color: var(--text);
  border-radius: 0.5rem;
  padding: 6px 10px;
}
.link {
  background: none;
  border: none;
  color: var(--accent);
  padding: 0;
}
.row-actions {
  display: flex;
  gap: 8px;
}
.status {
  margin: 0;
  color: var(--muted);
  font-size: 0.85rem;
}
.err {
  margin: 0;
  color: var(--danger);
  font-size: 0.85rem;
}
.industry h3 {
  margin: 0 0 8px;
  font-size: 0.9rem;
}
.muted {
  color: var(--muted);
  font-size: 0.75rem;
}
.toolbar {
  display: flex;
  gap: 12px;
  align-items: center;
  flex-wrap: wrap;
}
.toolbar .spacer {
  flex: 1;
}
.diff {
  color: var(--muted);
  font-size: 0.85rem;
}
.diff-summary {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
}
.diff-detail {
  margin-top: 8px;
  display: grid;
  gap: 8px;
}
.diff-group {
  display: grid;
  gap: 6px;
}
.diff-group strong {
  font-size: 0.8rem;
  color: var(--text);
}
.chip-link {
  background: var(--bg-panel);
  border: 1px solid var(--border);
  border-radius: 999px;
  padding: 4px 10px;
  font-size: 0.8rem;
  color: var(--text);
  cursor: pointer;
}
.chip-link:hover {
  border-color: var(--brand-soft);
  color: var(--brand);
}
.tip {
  margin: 0;
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
  border-bottom: 1px solid var(--border);
  font-size: 0.85rem;
  text-align: left;
  white-space: nowrap;
}
th {
  color: var(--muted);
  font-weight: 500;
  background: var(--surface-muted);
  position: sticky;
  top: 0;
}
th.sortable {
  cursor: pointer;
  user-select: none;
}
th.sortable:hover {
  color: var(--text);
}
.group-row th {
  padding: 4px 10px;
  font-size: 0.72rem;
  color: var(--ink-faint);
  background: var(--surface-muted);
  border-bottom: 1px solid var(--line);
  letter-spacing: 0.02em;
}
.col-row th {
  top: 24px;
  padding: 7px 10px;
}
.sel-col {
  text-align: center;
  width: 34px;
}
.ops-col {
  width: 96px;
}
.group-row th.g-quote,
.g-quote {
  background: rgba(230, 100, 50, 0.04);
}
.col-row th.g-quote {
  background: rgba(230, 100, 50, 0.06);
  color: var(--brand);
}
.group-row th.g-tape,
.g-tape {
  background: rgba(22, 163, 74, 0.03);
}
.col-row th.g-tape {
  background: rgba(22, 163, 74, 0.06);
  color: var(--ok);
}
.group-row th.g-fund,
.g-fund {
  background: rgba(115, 115, 115, 0.03);
}
.col-row th.g-fund {
  color: var(--ink-muted);
}
.group-row th.g-flow,
.g-flow {
  background: rgba(59, 130, 246, 0.04);
}
.col-row th.g-flow {
  background: rgba(59, 130, 246, 0.07);
  color: #2563eb;
}
.group-row th.g-score,
.g-score {
  background: rgba(230, 100, 50, 0.05);
}
.col-row th.g-score {
  background: rgba(230, 100, 50, 0.08);
  color: var(--brand);
}
.group-row th.g-quote,
.group-row th.g-tape,
.group-row th.g-fund,
.group-row th.g-flow,
.group-row th.g-score,
.col-row th.g-quote,
.col-row th.g-tape,
.col-row th.g-fund,
.col-row th.g-flow,
.col-row th.g-score,
td.g-quote,
td.g-tape,
td.g-fund,
td.g-flow,
td.g-score {
  border-left: 1px solid var(--line-soft);
}
td.g-flow {
  font-variant-numeric: tabular-nums;
}
td.g-score {
  font-weight: 500;
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
.chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.chip {
  background: var(--bg-panel);
  border: 1px solid var(--border);
  border-radius: 999px;
  padding: 4px 10px;
  font-size: 0.8rem;
}
</style>

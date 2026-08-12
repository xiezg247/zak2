# 选股 Hub 结果表排序过滤 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Hub 结果表展示行业列，支持表头排序与代码/名称/行业过滤（纯前端）。

**Architecture:** 在 `ScreenerHubView.vue` 用 `computed` 派生 `displayedRows`（先 filter 再 sort）；得分排序用多字段回落；CSV/`industry_dist` 仍用完整 `rows`。模式对齐 `WatchlistView` 列表排序过滤。

**Tech Stack:** Vue 3 `<script setup>`

**Spec:** `docs/superpowers/specs/2026-08-12-screener-hub-result-sort-filter-design.md`

## Global Constraints

- 只改 zak2；不改后端 / screener API
- CSV 与行业分布不过滤
- 空值排序垫底；得分键回落：`similarity_score` → `pattern_score` → `leader_score` → `score`
- commit message 简体中文：`<type>(<scope>): <简述>`

## File map

| 路径 | 职责 |
|------|------|
| `frontend/src/views/ScreenerHubView.vue` | 行业列、过滤、排序、空态 |
| `docs/smoke-checklist.md` / `product-roadmap.md` | 文档 |

---

### Task 1: ScreenerHubView displayedRows + UI

**Files:**
- Modify: `frontend/src/views/ScreenerHubView.vue`

**Interfaces:**
- Consumes: `rows` computed（`current.result.rows`）
- Produces: `displayedRows`；过滤/排序控件；行业列

- [ ] **Step 1: script — 状态与 helpers**

在 `rows` computed 附近增加（对齐 WatchlistView 风格）：

```typescript
type ResultSortKey = 'last_price' | 'change_pct' | 'turnover_rate' | 'volume_ratio' | 'score' | null

const resultFilter = ref('')
const sortKey = ref<ResultSortKey>(null)
const sortDir = ref<'asc' | 'desc'>('desc')

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

function cmpNullable(a: number | null | undefined, b: number | null | undefined, dir: 'asc' | 'desc'): number {
  const aMissing = a == null || Number.isNaN(a)
  const bMissing = b == null || Number.isNaN(b)
  if (aMissing && bMissing) return 0
  if (aMissing) return 1
  if (bMissing) return -1
  const d = (a as number) - (b as number)
  return dir === 'asc' ? d : -d
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
```

确认 `rows` 元素类型与现有 `v-for` 兼容（若原为宽松类型，保持 `as Record` 即可）。

- [ ] **Step 2: 结果区工具条（过滤 + 默认序）**

在结果 `<section>` 内、表格上方（`exportCsv` 按钮行附近）增加：

```html
<div class="row">
  <input v-model="resultFilter" placeholder="过滤代码/名称/行业" />
  <button v-if="sortKey" type="button" class="ghost" @click="clearSort">默认序</button>
  <button class="ghost" type="button" @click="exportCsv">导出 CSV</button>
</div>
```

（若已有仅含导出的 row，合并进同一 row，避免重复导出按钮。）

- [ ] **Step 3: 表头 / 行 / 空态**

- `v-for` 改为 `displayedRows`
- 名称后加 `<th>行业</th>` 与对应 `<td>{{ String(row.industry || '').trim() || '—' }}</td>`
- 可排序表头示例：

```html
<th class="sortable" @click="toggleSort('last_price')">现价{{ sortMark('last_price') }}</th>
<th class="sortable" @click="toggleSort('change_pct')">涨幅%{{ sortMark('change_pct') }}</th>
<th class="sortable" @click="toggleSort('turnover_rate')">换手%{{ sortMark('turnover_rate') }}</th>
<th class="sortable" @click="toggleSort('volume_ratio')">量比{{ sortMark('volume_ratio') }}</th>
<th class="sortable" @click="toggleSort('score')">得分{{ sortMark('score') }}</th>
```

- 空行：

```html
<tr v-if="!displayedRows.length">
  <td colspan="16" class="empty">
    {{ rows.length === 0 ? '运行选股后在此显示结果' : '无匹配结果' }}
  </td>
</tr>
```

- [ ] **Step 4: 样式**

复用或抄 WatchlistView 的 `.sortable { cursor: pointer; user-select: none; }`（若 Hub 尚无）。

- [ ] **Step 5: build**

```bash
cd frontend && npm run build
```

Expected: 成功

- [ ] **Step 6: Commit**

```bash
git add frontend/src/views/ScreenerHubView.vue
git commit -m "$(cat <<'EOF'
feat(screener): Hub 结果表支持行业列与排序过滤

纯前端 displayedRows；CSV 仍导出完整结果。
EOF
)"
```

---

### Task 2: 文档 + check.sh

**Files:**
- Modify: `docs/smoke-checklist.md`
- Modify: `docs/product-roadmap.md`

- [ ] **Step 1: smoke（§4 选股 Hub）**

```markdown
- [ ] Hub 结果表可见**行业**列；可按涨幅/得分等表头排序；可过滤代码/名称/行业；过滤无匹配显示「无匹配结果」；导出 CSV 仍为完整结果
```

- [ ] **Step 2: roadmap**

```markdown
13. ~~选股 Hub 结果表排序过滤~~（已完成 → [spec](./superpowers/specs/2026-08-12-screener-hub-result-sort-filter-design.md)）
```

- [ ] **Step 3: check.sh**

```bash
./scripts/check.sh
```

Expected: 全绿

- [ ] **Step 4: Commit**

```bash
git add docs/smoke-checklist.md docs/product-roadmap.md
git commit -m "$(cat <<'EOF'
docs: 记录选股 Hub 结果表排序过滤完成

更新 smoke 与路线图。
EOF
)"
```

---

## Spec coverage（自审）

| Spec | Task |
|------|------|
| 行业列 + 排序 + 过滤 + 空态 | 1 |
| CSV 不过滤 | 1（未改 export） |
| smoke / roadmap | 2 |

无 TBD。

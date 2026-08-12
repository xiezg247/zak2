# 自选列表扩列排序过滤 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 自选列表默认展示换手/量比/成交额；支持表头排序与代码/名称过滤（纯前端）。

**Architecture:** 在 `WatchlistView.vue` 内用 `computed` 派生 `displayedItems`（先 filter 再 sort）；成交额格式对齐市场页；不改后端。

**Tech Stack:** Vue 3 `<script setup>`、既有 `WatchlistItem` 类型

**Spec:** `docs/superpowers/specs/2026-08-12-watchlist-list-sort-filter-design.md`

## Global Constraints

- 只改 zak2；不改后端 / API 类型（字段已够）
- 不改策略看盘、持仓、分组 CRUD
- 空值排序垫底；成交额 `amount/1e8` → `x.xx亿`
- commit message 简体中文：`<type>(<scope>): <简述>`

## File map

| 路径 | 职责 |
|------|------|
| `frontend/src/views/WatchlistView.vue` | 过滤/排序/扩列/默认序 |
| `docs/smoke-checklist.md` | 检查项 |
| `docs/product-roadmap.md` | 可选完成记录 |

---

### Task 1: WatchlistView 扩列 + 排序 + 过滤

**Files:**
- Modify: `frontend/src/views/WatchlistView.vue`

**Interfaces:**
- Produces: `displayedItems` computed；`listFilter` / `sortKey` / `sortDir` refs；`formatAmountYi` / `cmpNullable` helpers
- Consumes: 现有 `items: WatchlistItem[]`

- [ ] **Step 1: 在 script 中增加状态与 helpers（`subtitle` computed 附近）**

```typescript
type SortKey = 'last_price' | 'change_pct' | 'turnover_rate' | 'volume_ratio' | 'amount' | null

const listFilter = ref('')
const sortKey = ref<SortKey>(null)
const sortDir = ref<'asc' | 'desc'>('desc')

function formatAmountYi(v: number | null | undefined): string {
  if (v == null || Number.isNaN(v)) return '—'
  return `${(v / 1e8).toFixed(2)}亿`
}

function formatNum2(v: number | null | undefined): string {
  if (v == null || Number.isNaN(v)) return '—'
  return v.toFixed(2)
}

function cmpNullable(a: number | null | undefined, b: number | null | undefined, dir: 'asc' | 'desc'): number {
  const aMissing = a == null || Number.isNaN(a)
  const bMissing = b == null || Number.isNaN(b)
  if (aMissing && bMissing) return 0
  if (aMissing) return 1 // 垫底
  if (bMissing) return -1
  const d = (a as number) - (b as number)
  return dir === 'asc' ? d : -d
}

function toggleSort(key: Exclude<SortKey, null>) {
  if (sortKey.value === key) {
    sortDir.value = sortDir.value === 'asc' ? 'desc' : 'asc'
  } else {
    sortKey.value = key
    sortDir.value = key === 'change_pct' || key === 'last_price' ? 'desc' : 'desc'
  }
}

function clearSort() {
  sortKey.value = null
}

const displayedItems = computed(() => {
  const q = listFilter.value.trim().toLowerCase()
  let rows = items.value
  if (q) {
    rows = rows.filter((it) => {
      const vt = (it.vt_symbol || '').toLowerCase()
      const name = (it.name || '').toLowerCase()
      return vt.includes(q) || name.includes(q)
    })
  }
  const key = sortKey.value
  if (!key) return rows
  const dir = sortDir.value
  return [...rows].sort((a, b) => cmpNullable(a[key], b[key], dir))
})

function sortMark(key: Exclude<SortKey, null>): string {
  if (sortKey.value !== key) return ''
  return sortDir.value === 'asc' ? ' ▲' : ' ▼'
}
```

- [ ] **Step 2: 改左侧列表模板**

在「自动刷新」与 error 之间（或 block 内）加过滤行：

```html
<div class="row">
  <input v-model="listFilter" placeholder="过滤代码/名称" />
  <button
    v-if="sortKey"
    type="button"
    class="ghost"
    @click="clearSort"
  >
    默认序
  </button>
</div>
```

表头改为可点排序（示例涨幅；其它数字列同理）：

```html
<th>代码</th>
<th>名称</th>
<th>行业</th>
<th class="sortable" @click="toggleSort('last_price')">现价{{ sortMark('last_price') }}</th>
<th class="sortable" @click="toggleSort('change_pct')">涨幅%{{ sortMark('change_pct') }}</th>
<th class="sortable" @click="toggleSort('turnover_rate')">换手%{{ sortMark('turnover_rate') }}</th>
<th class="sortable" @click="toggleSort('volume_ratio')">量比{{ sortMark('volume_ratio') }}</th>
<th class="sortable" @click="toggleSort('amount')">成交额{{ sortMark('amount') }}</th>
<th></th>
```

`tbody`：`v-for="item in displayedItems"`；空态 `colspan="9"`。

单元格：

```html
<td>{{ formatNum2(item.last_price) }}</td>
<td :class="{ up: (item.change_pct || 0) > 0, down: (item.change_pct || 0) < 0 }">
  {{ formatNum2(item.change_pct) }}
</td>
<td>{{ formatNum2(item.turnover_rate) }}</td>
<td>{{ formatNum2(item.volume_ratio) }}</td>
<td>{{ formatAmountYi(item.amount) }}</td>
```

- [ ] **Step 3: 样式**

```css
th.sortable {
  cursor: pointer;
  user-select: none;
}
th.sortable:hover {
  color: var(--text);
}
```

- [ ] **Step 4: 本地验证**

```bash
cd frontend && npm run build
```

Expected: 成功。手动：扩列可见；排序切换；过滤叠加；默认序；选中 K 线仍可用。

- [ ] **Step 5: Commit**

```bash
git add frontend/src/views/WatchlistView.vue
git commit -m "$(cat <<'EOF'
feat(watchlist): 自选列表扩列并支持排序与过滤

展示换手/量比/成交额；表头排序；代码名称过滤。
EOF
)"
```

---

### Task 2: 文档 + check.sh

**Files:**
- Modify: `docs/smoke-checklist.md`
- Modify: `docs/product-roadmap.md`（近期待办加完成项）

- [ ] **Step 1: smoke**

在「自选 · 行情」增加：

```markdown
- [ ] `/watchlist` 列表可见换手%/量比/成交额；点涨幅等表头可排序；「默认序」恢复；过滤框可按代码/名称缩小列表
```

- [ ] **Step 2: roadmap**

增加完成项，例如：

`9. ~~自选列表扩列排序过滤~~（已完成 → [spec](./superpowers/specs/2026-08-12-watchlist-list-sort-filter-design.md)）`

- [ ] **Step 3: check.sh**

```bash
./scripts/check.sh
```

Expected: pytest + frontend build OK

- [ ] **Step 4: Commit**

```bash
git add docs/smoke-checklist.md docs/product-roadmap.md
git commit -m "$(cat <<'EOF'
docs: 记录自选列表扩列排序过滤完成

更新 smoke 与路线图。
EOF
)"
```

---

## Spec coverage（自审）

| Spec | Task |
|------|------|
| 扩列换手/量比/额 | 1 |
| 排序 + 默认序 + 空值垫底 | 1 |
| 过滤 | 1 |
| smoke / roadmap / build | 2 |

无 TBD。

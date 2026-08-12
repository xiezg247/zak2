# 板块资金表过滤排序 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 板块资金表支持名称/ID 过滤、涨幅/净流入列头排序，并区分真无数据与无匹配空态。

**Architecture:** 纯前端 `displayedRows` 管道（filter → sort）；toolbar 请求参数不变；「默认序」= 当前 API 返回序。

**Tech Stack:** Vue 3

**Spec:** `docs/superpowers/specs/2026-08-12-sector-flow-sort-filter-design.md`

## Global Constraints

- 只改 zak2；不改 sector API / 市场页 / 雷达
- 真无数据与「无匹配板块」分支分开
- 不点行下钻、不新成分 API
- commit message 简体中文：`<type>(<scope>): <简述>`

## File map

| 路径 | 职责 |
|------|------|
| `frontend/src/views/SectorView.vue` | 管道 + UI |
| `docs/smoke-checklist.md` / `product-roadmap.md` | 文档 |

对齐参考：`WatchlistView.vue` 的 `cmpNullable` / `toggleSort` / `displayedItems`。

---

### Task 1: SectorView displayedRows + UI

**Files:**
- Modify: `frontend/src/views/SectorView.vue`

- [ ] **Step 1: 状态与 computed**

在 `rows` / `loading` 附近增加（类型可内联）：

```typescript
type SortKey = 'change_pct' | 'net_flow_yi' | null

const listFilter = ref('')
const sortKey = ref<SortKey>(null)
const sortDir = ref<'asc' | 'desc'>('desc')

function cmpNullable(a: number | null | undefined, b: number | null | undefined, dir: 'asc' | 'desc'): number {
  const aMissing = a == null || Number.isNaN(a)
  const bMissing = b == null || Number.isNaN(b)
  if (aMissing && bMissing) return 0
  if (aMissing) return 1
  if (bMissing) return -1
  const d = (a as number) - (b as number)
  return dir === 'asc' ? d : -d
}

function toggleSort(key: Exclude<SortKey, null>) {
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

function sortMark(key: Exclude<SortKey, null>): string {
  if (sortKey.value !== key) return ''
  return sortDir.value === 'asc' ? ' ▲' : ' ▼'
}

const displayedRows = computed(() => {
  const q = listFilter.value.trim().toLowerCase()
  let list = rows.value
  if (q) {
    list = list.filter((r) => {
      const name = (r.name || '').toLowerCase()
      const id = (r.sector_id || '').toLowerCase()
      return name.includes(q) || id.includes(q)
    })
  }
  const key = sortKey.value
  if (!key) return list
  const dir = sortDir.value
  return [...list].sort((a, b) => cmpNullable(a[key], b[key], dir))
})
```

- [ ] **Step 2: 模板 — 过滤条 + 空态 + 表头**

在 toolbar 与 error/loading 之后、`table-wrap` 之前（有数据时）：

```html
<div v-if="rows.length" class="filter-row">
  <input v-model="listFilter" placeholder="过滤名称/ID" />
  <button type="button" class="ghost" :class="{ on: !sortKey }" @click="clearSort">默认序</button>
</div>
```

加载 / 真无数据 / 无匹配：

```html
<p v-if="loading" class="muted">加载中…</p>
<p v-else-if="!error && !rows.length" class="muted empty-hint">
  暂无板块资金。可先到 Ops 执行 sync_sector_flow_daily。
</p>
<p v-else-if="rows.length && !displayedRows.length" class="muted empty-hint">无匹配板块</p>
```

表格：`v-if="displayedRows.length"`（或 `rows.length && displayedRows.length`），`v-for="(r, i) in displayedRows"`，`#` 用 `i + 1`。

表头：

```html
<th class="sortable" @click="toggleSort('change_pct')">涨幅%{{ sortMark('change_pct') }}</th>
<th class="sortable" @click="toggleSort('net_flow_yi')">净流入(亿){{ sortMark('net_flow_yi') }}</th>
```

去掉原 tbody 内「暂无板块资金」空行（改由上方空态承担）；若保留 table 骨架在无匹配时可不渲染 tbody 空行。

- [ ] **Step 3: 样式**

```css
.filter-row { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
.filter-row input {
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: 0.5rem;
  color: var(--text);
  padding: 6px 10px;
  min-width: 160px;
}
.ghost {
  background: transparent;
  border: 1px solid var(--border);
  color: var(--muted);
  border-radius: 0.5rem;
  padding: 6px 10px;
  cursor: pointer;
}
.ghost.on { border-color: var(--brand, #333); color: var(--text); font-weight: 500; }
th.sortable { cursor: pointer; user-select: none; }
.empty-hint { margin: 0; padding: 12px 0; }
```

（若文件已有近似类名则复用，避免冲突。）

- [ ] **Step 4: build**

```bash
cd frontend && npm run build
```

Expected: 成功

- [ ] **Step 5: Commit**

```bash
git add frontend/src/views/SectorView.vue
git commit -m "$(cat <<'EOF'
feat(sectors): 板块资金表支持过滤与列排序

纯前端 displayedRows；无匹配与真无数据空态分离。
EOF
)"
```

---

### Task 2: 文档 + check.sh

**Files:**
- Modify: `docs/smoke-checklist.md`
- Modify: `docs/product-roadmap.md`

- [ ] **Step 1: smoke（§5，紧接现有 `/sectors` 条）**

```markdown
- [ ] `/sectors` 有数据时可按名称/ID 过滤与涨幅·净流入列排序；无匹配显示「无匹配板块」；真无数据仍见暂无提示
```

- [ ] **Step 2: roadmap**

```markdown
19. ~~板块资金表过滤排序~~（已完成 → [spec](./superpowers/specs/2026-08-12-sector-flow-sort-filter-design.md)）
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
docs: 记录板块资金表过滤排序完成

更新 smoke 与路线图。
EOF
)"
```

---

## Spec coverage（自审）

| Spec | Task |
|------|------|
| filter + 列排序 + 默认序 + 空态 | 1 |
| smoke / roadmap | 2 |

无 TBD。

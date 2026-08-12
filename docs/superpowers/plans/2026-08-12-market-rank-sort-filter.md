# 市场排行过滤排序 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 市场排行表支持代码/名称过滤、现价/涨幅/当前分数字段列头排序；过滤隐藏时保留选中详情。

**Architecture:** 纯前端 `displayedRanks`（filter → sort）；field tabs 请求不变；「默认序」= API 返回序。

**Tech Stack:** Vue 3

**Spec:** `docs/superpowers/specs/2026-08-12-market-rank-sort-filter-design.md`

## Global Constraints

- 只改 zak2；不改 ranks API / 情绪阈值 / 板块页
- 过滤隐藏选中行时保留 `selected` 与右侧详情
- `field === 'change_pct'` 时动态列不重复挂排序
- commit message 简体中文：`<type>(<scope>): <简述>`

## File map

| 路径 | 职责 |
|------|------|
| `frontend/src/views/MarketView.vue` | 管道 + UI |
| `docs/smoke-checklist.md` / `product-roadmap.md` | 文档 |

对齐参考：`WatchlistView.vue` / `SectorView.vue` 的 `cmpNullable` / `toggleSort`。

---

### Task 1: MarketView displayedRanks + UI

**Files:**
- Modify: `frontend/src/views/MarketView.vue`

- [ ] **Step 1: 状态与 computed**

靠近 `ranks` / `field`：

```typescript
type SortKey =
  | 'last_price'
  | 'change_pct'
  | 'turnover_rate'
  | 'amount'
  | 'volume_ratio'
  | 'limit_times'
  | null

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

/** 当前 field tab 下动态列是否可点排序（涨幅 tab 时否） */
const scoreSortKey = computed((): Exclude<SortKey, null> | null => {
  const id = field.value
  if (id === 'change_pct') return null
  if (id === 'turnover_rate' || id === 'amount' || id === 'volume_ratio' || id === 'limit_times') {
    return id
  }
  return null
})

const displayedRanks = computed(() => {
  const q = listFilter.value.trim().toLowerCase()
  let list = ranks.value
  if (q) {
    list = list.filter((r) => {
      const vt = (r.vt_symbol || '').toLowerCase()
      const name = (r.name || '').toLowerCase()
      return vt.includes(q) || name.includes(q)
    })
  }
  const key = sortKey.value
  if (!key) return list
  const dir = sortDir.value
  return [...list].sort((a, b) => cmpNullable(a[key], b[key], dir))
})
```

切换 `field` 时若当前 `sortKey` 是动态分数字段且已不等于新 `scoreSortKey`，可保留（YAGNI）；若 `sortKey` 指向已不可用的动态列，排序仍按该字段数值比（行上字段仍在）——可接受。更干净：在 `watch(field)` 里若 `sortKey` 为动态字段且 !== 新 field，则 `clearSort()`——**推荐加一行**：

```typescript
watch(field, () => {
  const sk = sortKey.value
  if (sk && sk !== 'last_price' && sk !== 'change_pct' && sk !== field.value) {
    sortKey.value = null
  }
  void onField()
})
```

（合并进现有 `watch(field)`，勿重复注册。）

- [ ] **Step 2: 模板**

在 `split` / `table-wrap` 前（有 ranks 时）：

```html
<div v-if="ranks.length" class="filter-row">
  <input v-model="listFilter" placeholder="过滤代码/名称" />
  <button type="button" class="ghost" :class="{ on: !sortKey }" @click="clearSort">默认序</button>
</div>
```

表头：

```html
<th>#</th>
<th>代码</th>
<th>名称</th>
<th class="sortable" @click="toggleSort('last_price')">现价{{ sortMark('last_price') }}</th>
<th class="sortable" @click="toggleSort('change_pct')">涨幅%{{ sortMark('change_pct') }}</th>
<th
  v-if="scoreSortKey"
  class="sortable"
  @click="toggleSort(scoreSortKey)"
>
  {{ fieldMeta.col }}{{ sortMark(scoreSortKey) }}
</th>
<th v-else>{{ fieldMeta.col }}</th>
```

tbody：`v-for="(r, i) in displayedRanks"`，`#` 用 `i + 1`；空行：

```html
<tr v-if="!ranks.length">
  <td colspan="6" class="empty">暂无排行（需 Redis 行情快照）</td>
</tr>
<tr v-else-if="!displayedRanks.length">
  <td colspan="6" class="empty">无匹配标的</td>
</tr>
```

（或无匹配时在表外用 `p.muted`，与 SectorView 一致亦可；二选一，推荐表外 `p` + `v-if="displayedRanks.length"` 包 table 主体，过滤条在无匹配时仍可见。）

推荐结构（对齐 SectorView）：

```html
<div v-if="ranks.length" class="filter-row">...</div>
<p v-if="ranks.length && !displayedRanks.length" class="muted empty-hint">无匹配标的</p>
<div class="split" v-else>
  <div class="table-wrap">
    <table>
      ...
      <tbody>
        <tr v-for="(r, i) in displayedRanks" ...>
          <td>{{ i + 1 }}</td>
          ...
        </tr>
        <tr v-if="!ranks.length">
          <td colspan="6" class="empty">暂无排行（需 Redis 行情快照）</td>
        </tr>
      </tbody>
    </table>
  </div>
  <aside ...> <!-- selected 详情：无匹配时也要显示，故不能整块 v-else 掉 detail -->
```

**注意：** 无匹配时仍需显示右侧 `selected` 详情。因此 **不要** 用 `v-else` 整块藏掉 `split`。正确做法：

- 过滤条：`v-if="ranks.length"`
- 无匹配提示：`v-if="ranks.length && !displayedRanks.length"`
- `split` **始终**在（或至少 detail 始终可显）：table 内无匹配时空 tbody + 提示，或 table-wrap 内提示；`aside` 仍 `v-if="selected"`

推荐：

```html
<div v-if="ranks.length" class="filter-row">...</div>
<p v-if="error" class="err">...</p>
<div class="split">
  <div class="table-wrap">
    <p v-if="ranks.length && !displayedRanks.length" class="muted empty-hint">无匹配标的</p>
    <table v-else>
      ...
      <tr v-for="(r, i) in displayedRanks" ...>
      <tr v-if="!ranks.length"><td colspan="6" class="empty">暂无排行...</td></tr>
    </table>
  </div>
  <aside v-if="selected" class="detail">...</aside>
  <aside v-else class="detail empty-panel">...</aside>
</div>
```

- [ ] **Step 3: 样式**

复用/补 `.filter-row`、`.ghost.on`、`th.sortable`、`.empty-hint`（可参考 `SectorView.vue`）。

- [ ] **Step 4: build**

```bash
cd frontend && npm run build
```

Expected: 成功

- [ ] **Step 5: Commit**

```bash
git add frontend/src/views/MarketView.vue
git commit -m "$(cat <<'EOF'
feat(market): 排行表支持过滤与列排序

纯前端 displayedRanks；过滤隐藏时仍保留选中详情。
EOF
)"
```

---

### Task 2: 文档 + check.sh

**Files:**
- Modify: `docs/smoke-checklist.md`
- Modify: `docs/product-roadmap.md`

- [ ] **Step 1: smoke（§5，紧接现有 `/market` 情绪条）**

```markdown
- [ ] `/market` 有排行时可按代码/名称过滤与现价·涨幅·当前分数字段列排序；无匹配显示「无匹配标的」；过滤掉选中行后详情仍保留
```

- [ ] **Step 2: roadmap**

```markdown
20. ~~市场排行过滤排序~~（已完成 → [spec](./superpowers/specs/2026-08-12-market-rank-sort-filter-design.md)）
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
docs: 记录市场排行过滤排序完成

更新 smoke 与路线图。
EOF
)"
```

---

## Spec coverage（自审）

| Spec | Task |
|------|------|
| filter + 列排序 + 默认序 + 选中保留 + 空态 | 1 |
| smoke / roadmap | 2 |

无 TBD。特别注意：无匹配时 **不得** 用外层 `v-else` 藏掉 detail。

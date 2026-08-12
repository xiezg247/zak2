# 自选列表列偏好 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 自选列表可开关行业/换手%/量比/成交额列，偏好写入 localStorage。

**Architecture:** `colVisible` reactive + 「列」面板；读写 `zak2:watchlist:list_columns`；隐藏列时清相关 sort。

**Tech Stack:** Vue 3、localStorage

**Spec:** `docs/superpowers/specs/2026-08-12-watchlist-column-prefs-design.md`

## Global Constraints

- 只改 zak2；不改后端 prefs API
- 核心列（代码/名称/现价/涨幅%/删）始终显示
- 不改分组/策略看盘/持仓表
- commit message 简体中文：`<type>(<scope>): <简述>`

## File map

| 路径 | 职责 |
|------|------|
| `frontend/src/views/WatchlistView.vue` | 列面板 + 显隐 + localStorage |
| `docs/smoke-checklist.md` / `product-roadmap.md` | 文档 |

---

### Task 1: WatchlistView 列偏好

**Files:**
- Modify: `frontend/src/views/WatchlistView.vue`

- [ ] **Step 1: 常量与状态**

靠近 `listFilter` / `sortKey`：

```typescript
const COL_PREFS_KEY = 'zak2:watchlist:list_columns'

type OptionalCol = 'industry' | 'turnover_rate' | 'volume_ratio' | 'amount'

const DEFAULT_COL_VISIBLE: Record<OptionalCol, boolean> = {
  industry: true,
  turnover_rate: true,
  volume_ratio: true,
  amount: true,
}

const columnsOpen = ref(false)
const colVisible = ref<Record<OptionalCol, boolean>>({ ...DEFAULT_COL_VISIBLE })

function loadColPrefs() {
  try {
    const raw = localStorage.getItem(COL_PREFS_KEY)
    if (!raw) return
    const parsed = JSON.parse(raw) as Partial<Record<OptionalCol, unknown>>
    const next = { ...DEFAULT_COL_VISIBLE }
    for (const k of Object.keys(DEFAULT_COL_VISIBLE) as OptionalCol[]) {
      if (typeof parsed[k] === 'boolean') next[k] = parsed[k] as boolean
    }
    colVisible.value = next
  } catch {
    colVisible.value = { ...DEFAULT_COL_VISIBLE }
  }
}

function saveColPrefs() {
  localStorage.setItem(COL_PREFS_KEY, JSON.stringify(colVisible.value))
}

function setColVisible(key: OptionalCol, on: boolean) {
  colVisible.value = { ...colVisible.value, [key]: on }
  if (!on && sortKey.value === key) clearSort()
  saveColPrefs()
}

const optionalColLabels: { key: OptionalCol; label: string }[] = [
  { key: 'industry', label: '行业' },
  { key: 'turnover_rate', label: '换手%' },
  { key: 'volume_ratio', label: '量比' },
  { key: 'amount', label: '成交额' },
]

const tableColspan = computed(() => {
  // 代码 名称 现价 涨幅% 删 = 5；加可选开着的列
  let n = 5
  for (const k of Object.keys(DEFAULT_COL_VISIBLE) as OptionalCol[]) {
    if (colVisible.value[k]) n += 1
  }
  return n
})
```

在现有 `onMounted`（或列表相关 mount）调用 `loadColPrefs()`。

- [ ] **Step 2: 工具条「列」面板**

在过滤 `row` 内：

```html
<div class="row col-prefs-row">
  <input v-model="listFilter" placeholder="过滤代码/名称" />
  <button v-if="sortKey" type="button" class="ghost" @click="clearSort">默认序</button>
  <button type="button" class="ghost" :class="{ on: columnsOpen }" @click="columnsOpen = !columnsOpen">
    列
  </button>
</div>
<div v-if="columnsOpen" class="col-prefs-panel">
  <label v-for="c in optionalColLabels" :key="c.key" class="col-pref-item">
    <input
      type="checkbox"
      :checked="colVisible[c.key]"
      @change="setColVisible(c.key, ($event.target as HTMLInputElement).checked)"
    />
    {{ c.label }}
  </label>
</div>
```

（若项目避免 `as` 断言，可用 `(e: Event) => setColVisible(c.key, (e.target as HTMLInputElement).checked)` 包一层函数。）

- [ ] **Step 3: 表头/表体 v-if**

```html
<th>代码</th>
<th>名称</th>
<th v-if="colVisible.industry">行业</th>
<th class="sortable" @click="toggleSort('last_price')">现价{{ sortMark('last_price') }}</th>
<th class="sortable" @click="toggleSort('change_pct')">涨幅%{{ sortMark('change_pct') }}</th>
<th v-if="colVisible.turnover_rate" class="sortable" @click="toggleSort('turnover_rate')">
  换手%{{ sortMark('turnover_rate') }}
</th>
<th v-if="colVisible.volume_ratio" class="sortable" @click="toggleSort('volume_ratio')">
  量比{{ sortMark('volume_ratio') }}
</th>
<th v-if="colVisible.amount" class="sortable" @click="toggleSort('amount')">
  成交额{{ sortMark('amount') }}
</th>
<th></th>
```

tbody 对应 `<td v-if="colVisible.industry">` 等；空行：

```html
<tr v-if="!displayedItems.length">
  <td :colspan="tableColspan" class="empty">…现有空态文案…</td>
</tr>
```

- [ ] **Step 4: 样式**

```css
.col-prefs-panel {
  display: flex;
  flex-wrap: wrap;
  gap: 10px 14px;
  padding: 8px 0;
  font-size: 0.85rem;
  color: var(--muted);
}
.col-pref-item {
  display: flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
}
.ghost.on {
  border-color: var(--brand, var(--accent));
  color: var(--text);
}
```

（若已有 `.ghost.on` 则复用。）

- [ ] **Step 5: build**

```bash
cd frontend && npm run build
```

Expected: 成功

- [ ] **Step 6: Commit**

```bash
git add frontend/src/views/WatchlistView.vue
git commit -m "$(cat <<'EOF'
feat(watchlist): 自选列表支持列显示偏好

可选列勾选写入 localStorage；隐藏列时清除相关排序。
EOF
)"
```

---

### Task 2: 文档 + check.sh

**Files:**
- Modify: `docs/smoke-checklist.md`
- Modify: `docs/product-roadmap.md`

- [ ] **Step 1: smoke（紧接现有列表排序过滤条）**

```markdown
- [ ] `/watchlist`「列」可关行业/换手/量比/成交额并刷新后保留；代码名称现价涨幅始终可见；关闭正在排序的列回到默认序
```

- [ ] **Step 2: roadmap**

```markdown
25. ~~自选列表列偏好~~（已完成 → [spec](./superpowers/specs/2026-08-12-watchlist-column-prefs-design.md)）
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
docs: 记录自选列表列偏好完成

更新 smoke 与路线图。
EOF
)"
```

---

## Spec coverage（自审）

| Spec | Task |
|------|------|
| 列面板 + localStorage + 显隐 + 清排序 | 1 |
| smoke / roadmap | 2 |

无 TBD。

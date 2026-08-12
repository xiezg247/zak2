# 选股 Hub 批量入自选 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Hub 结果表支持勾选与一键批量加入自选（串行现有 POST；409 计跳过）。

**Architecture:** 纯前端：`selectedVts` + 表头/行 checkbox + `addSelectedToWatchlist` 串行 `watchlistApi.add`；打开新 run 清空勾选；过滤变化 prune。

**Tech Stack:** Vue 3

**Spec:** `docs/superpowers/specs/2026-08-12-screener-hub-batch-watchlist-design.md`

## Global Constraints

- 只改 zak2；不新增批量 API / 不改后端
- 409「已在自选中」→ skip；其它错误 → fail 并继续
- 全选范围 = `displayedRows`；`colspan` 16→17
- commit message 简体中文：`<type>(<scope>): <简述>`

## File map

| 路径 | 职责 |
|------|------|
| `frontend/src/views/ScreenerHubView.vue` | 勾选 + 批量加入 |
| `docs/smoke-checklist.md` / `product-roadmap.md` | 文档 |

---

### Task 1: ScreenerHubView 勾选与批量加入

**Files:**
- Modify: `frontend/src/views/ScreenerHubView.vue`

- [ ] **Step 1: 状态与 helpers**

靠近结果过滤相关 ref：

```typescript
const selectedVts = ref<Record<string, true>>({})
const batchBusy = ref(false)

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
```

- [ ] **Step 2: watch / openRun / pollJob 挂钩**

```typescript
watch(displayedRows, () => pruneSelectedToDisplayed())

// openRun 成功分支已有 resultFilter=''；追加：
clearSelected()

// pollJob 成功 current.value = ... 后追加：
clearSelected()
```

（若 `watch(displayedRows)` 在 openRun 清空后立即 prune 无害。）

- [ ] **Step 3: addSelectedToWatchlist**

```typescript
async function addSelectedToWatchlist() {
  const list = displayedRows.value as Record<string, unknown>[]
  const queue = list.filter((row) => {
    const vt = rowVt(row)
    return vt && isSelected(vt)
  })
  if (!queue.length || batchBusy.value) return
  batchBusy.value = true
  error.value = ''
  let ok = 0
  let skip = 0
  let fail = 0
  try {
    for (const row of queue) {
      const vt = rowVt(row)
      const name = String(row.name || '')
      try {
        await watchlistApi.add(vt, name)
        ok++
      } catch (e) {
        const msg = e instanceof Error ? e.message : ''
        if (msg.includes('已在自选中')) skip++
        else fail++
      }
    }
    statusText.value = `已加入 ${ok} · 已在自选 ${skip} · 失败 ${fail}`
    if (fail > 0) error.value = '部分加入失败，见上方汇总'
  } finally {
    batchBusy.value = false
  }
}
```

确认文件已 `import { watchlistApi } from ...`（单行自选已用）。

- [ ] **Step 4: 模板**

工具条（filter-row）增加按钮：

```html
<button
  type="button"
  class="ghost"
  :disabled="batchBusy || selectedCount === 0"
  @click="addSelectedToWatchlist"
>
  {{ batchBusy ? '加入中…' : `加入自选 (${selectedCount})` }}
</button>
```

表头首列：

```html
<th>
  <input
    type="checkbox"
    :checked="allDisplayedSelected"
    :disabled="!displayedRows.length"
    @change="toggleSelectAllDisplayed"
  />
</th>
```

行首列：

```html
<td @click.stop>
  <input
    type="checkbox"
    :checked="isSelected(rowVt(row))"
    @change="toggleVt(rowVt(row))"
  />
</td>
```

空行 `colspan="17"`。

- [ ] **Step 5: build**

```bash
cd frontend && npm run build
```

Expected: 成功

- [ ] **Step 6: Commit**

```bash
git add frontend/src/views/ScreenerHubView.vue
git commit -m "$(cat <<'EOF'
feat(screener): Hub 结果支持批量加入自选

勾选/全选当前过滤结果；串行 add，409 计跳过。
EOF
)"
```

---

### Task 2: 文档 + check.sh

**Files:**
- Modify: `docs/smoke-checklist.md`
- Modify: `docs/product-roadmap.md`

- [ ] **Step 1: smoke（§4）**

```markdown
- [ ] Hub 结果可勾选/全选当前过滤结果；「加入自选 (N)」批量加入并见「已加入/已在自选/失败」汇总；单行「自选」仍可用
```

- [ ] **Step 2: roadmap**

```markdown
15. ~~选股 Hub 批量入自选~~（已完成 → [spec](./superpowers/specs/2026-08-12-screener-hub-batch-watchlist-design.md)）
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
docs: 记录选股 Hub 批量入自选完成

更新 smoke 与路线图。
EOF
)"
```

---

## Spec coverage（自审）

| Spec | Task |
|------|------|
| 勾选/全选/批量/生命周期 | 1 |
| smoke / roadmap | 2 |

无 TBD。

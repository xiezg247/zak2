# 回测历史过滤与空态 UX Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `/backtest` 历史按标的/策略过滤，区分加载中/无历史/无匹配，并高亮当前选中 run。

**Architecture:** 纯前端 `displayedRuns` / `displayedBatches`（对齐 NotesView）；保持 `selected`。

**Tech Stack:** Vue 3 `computed` / `ref`。

**Spec:** `docs/superpowers/specs/2026-08-13-backtest-history-filter-ux-design.md`

## Global Constraints

- 只改 `BacktestView.vue` + smoke + roadmap
- 不改 backtest API
- Commit 简体中文；不 push

---

### Task 1: BacktestView 过滤 + 空态 + 高亮

**Files:**
- Modify: `frontend/src/views/BacktestView.vue`

- [ ] **Step 1: 状态与 computed**

```typescript
const listFilter = ref('')
const loading = ref(false)

const displayedRuns = computed(() => {
  const q = listFilter.value.trim().toLowerCase()
  let list = runs.value
  if (q) {
    list = list.filter((r) => {
      const vt = (r.vt_symbol || '').toLowerCase()
      const st = (r.strategy || '').toLowerCase()
      return vt.includes(q) || st.includes(q)
    })
  }
  return list.slice(0, 30)
})

const displayedBatches = computed(() => {
  const q = listFilter.value.trim().toLowerCase()
  if (!q) return batches.value
  return batches.value.filter((b) => (b.strategy || '').toLowerCase().includes(q))
})
```

- [ ] **Step 2: loading 包裹 refresh / onMounted**

```typescript
async function refresh() {
  loading.value = true
  error.value = ''
  try {
    const [s, p, r, b] = await Promise.all([
      backtestApi.strategies(),
      backtestApi.profiles(),
      backtestApi.runs(),
      backtestApi.batches(),
    ])
    strategies.value = s
    profiles.value = p
    runs.value = r
    batches.value = b
  } finally {
    loading.value = false
  }
}
```

（`onMounted` 仍调 `refresh`；若 `refresh` 在 poll 成功后调用，短暂 loading 可接受，或仅 `onMounted` 设 loading——**推荐**：仅在 `onMounted` 路径设 loading，避免每次 poll 闪烁：

```typescript
async function refresh() { /* 无 loading，逻辑同现 */ }

onMounted(async () => {
  loading.value = true
  try {
    await refresh()
  } catch (e) {
    error.value = e instanceof Error ? e.message : '加载失败'
  } finally {
    loading.value = false
  }
})
```

）

- [ ] **Step 3: 模板历史区**

```vue
<h3>历史</h3>
<input
  v-if="runs.length"
  v-model="listFilter"
  class="filter"
  placeholder="过滤标的/策略"
/>
<p v-if="loading" class="empty muted">加载中…</p>
<template v-else>
  <p v-if="!runs.length" class="empty muted">暂无回测历史</p>
  <p v-else-if="!displayedRuns.length" class="empty muted">无匹配历史</p>
  <button
    v-for="r in displayedRuns"
    :key="r.id"
    type="button"
    class="hist"
    :class="{ on: selected?.id === r.id }"
    @click="openRun(r.id)"
  >
    <!-- 现有两行内容 -->
  </button>
</template>

<h3 v-if="batches.length">批次对比</h3>
<p
  v-if="batches.length && listFilter.trim() && !displayedBatches.length"
  class="empty muted"
>
  无匹配批次
</p>
<button
  v-for="b in displayedBatches"
  :key="b.batch_id"
  type="button"
  class="hist"
  @click="openBatch(b.batch_id)"
>
  <!-- 现有 -->
</button>
```

- [ ] **Step 4: 右侧空态**

```vue
<p v-if="loading" class="empty muted">加载中…</p>
<p v-else-if="!selected && !compare.length" class="empty muted">
  运行回测或从左侧打开历史记录
</p>
```

（`selected` / `compare` 块保持；loading 时若已有 selected 可仍显示详情——**推荐** loading 仅影响无选中空态文案，有 selected 优先详情。）

更简：右侧原 empty 改为：

```vue
<p v-if="!selected && !compare.length" class="empty muted">
  {{ loading ? '加载中…' : '运行回测或从左侧打开历史记录' }}
</p>
```

- [ ] **Step 5: 样式**

```css
.filter {
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 0.5rem;
  color: var(--text);
  padding: 8px 10px;
  width: 100%;
}
.hist.on {
  border-color: var(--accent);
}
```

- [ ] **Step 6: 构建**

```bash
cd frontend && npm run build
```

Expected: 成功。

- [ ] **Step 7: Commit**

```bash
git add frontend/src/views/BacktestView.vue
git commit -m "$(cat <<'EOF'
feat(backtest): 历史按标的/策略过滤并区分空态

对齐笔记侧栏体验，选中 run 高亮。
EOF
)"
```

---

### Task 2: smoke + roadmap + check.sh

**Files:**
- Modify: `docs/smoke-checklist.md`
- Modify: `docs/product-roadmap.md`

- [ ] **Step 1: smoke**

在现有 `/backtest` 条附近增加：

```markdown
- [ ] `/backtest` 有历史时可按标的/策略过滤；无匹配见「无匹配历史」；无历史见「暂无回测历史」；加载中可见提示；打开某条历史该项高亮
```

- [ ] **Step 2: roadmap #33**

```markdown
33. ~~回测历史过滤与空态~~（已完成 → [spec](./superpowers/specs/2026-08-13-backtest-history-filter-ux-design.md)）
```

- [ ] **Step 3: check.sh**

```bash
./scripts/check.sh
```

Expected: `OK：测试与构建通过`

- [ ] **Step 4: Commit**

```bash
git add docs/smoke-checklist.md docs/product-roadmap.md
git commit -m "$(cat <<'EOF'
docs: 记录回测历史过滤空态完成

更新 smoke 与路线图 #33。
EOF
)"
```

---

## Spec coverage（自审）

| Spec | Task |
|------|------|
| displayedRuns / Batches | 1 |
| 空态 + loading | 1 |
| 选中高亮 | 1 |
| 保持 selected | 1 |
| smoke + #33 | 2 |

无 TBD。loading 仅 `onMounted`，避免 poll 闪烁。

---

# BHF SDD progress

- Task 1: done @ 59f69e3 (approved)
- Task 2: done @ 47ec17c (approved)
- Final review: APPROVED

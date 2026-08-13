# 笔记侧栏过滤与空态 UX Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `/notes` 左侧按代码/备忘预览过滤，并区分加载中 / 暂无标的 / 无匹配空态。

**Architecture:** 纯前端 `displayedSymbols`（对齐 Feed `displayedItems`）；保持 `selected` 被滤掉时详情仍可读。

**Tech Stack:** Vue 3 `computed` / `ref`。

**Spec:** `docs/superpowers/specs/2026-08-13-notes-sidebar-filter-ux-design.md`

## Global Constraints

- 只改 `NotesView.vue` + smoke + roadmap（本 plan 两 task）
- 不改 notes API；不改研报 / 删流水
- 过滤框仅在 `symbols.length > 0` 时显示
- Commit 简体中文；不 push

---

### Task 1: NotesView 过滤 + 空态

**Files:**
- Modify: `frontend/src/views/NotesView.vue`

**Interfaces:**
- Consumes: 现有 `symbols` / `selected` / `loadSymbols` / `loadDetail`
- Produces: `listFilter`、`loading`、`displayedSymbols`

- [ ] **Step 1: 状态与 computed**

在 script 中：

```typescript
import { computed, onMounted, ref, watch } from 'vue'
// ...
const listFilter = ref('')
const loading = ref(false)

const displayedSymbols = computed(() => {
  const q = listFilter.value.trim().toLowerCase()
  if (!q) return symbols.value
  return symbols.value.filter((s) => {
    const vt = (s.vt_symbol || '').toLowerCase()
    const preview = (s.memo_preview || '').toLowerCase()
    return vt.includes(q) || preview.includes(q)
  })
})
```

- [ ] **Step 2: loading 包裹首次加载**

```typescript
onMounted(async () => {
  loading.value = true
  error.value = ''
  try {
    const qSym = String(route.query.symbol || '').trim()
    if (qSym) selected.value = qSym
    await loadSymbols()
    await loadDetail()
  } catch (e) {
    error.value = e instanceof Error ? e.message : '加载失败'
  } finally {
    loading.value = false
  }
})
```

（若原 `onMounted` 已有 try/catch，合并进上述结构，避免双重套。）

- [ ] **Step 3: 模板左侧**

在「打开」行之后：

```vue
<input
  v-if="symbols.length"
  v-model="listFilter"
  class="filter"
  placeholder="过滤代码/备忘"
/>
<p v-if="loading" class="empty muted">加载中…</p>
<template v-else>
  <p v-if="!symbols.length" class="hint muted">输入代码打开笔记</p>
  <p v-else-if="!displayedSymbols.length" class="empty muted">无匹配标的</p>
  <button
    v-for="s in displayedSymbols"
    :key="s.vt_symbol"
    type="button"
    class="sym"
    :class="{ on: selected === s.vt_symbol }"
    @click="selected = s.vt_symbol"
  >
    <!-- 现有内容不变 -->
  </button>
</template>
```

- [ ] **Step 4: 模板右侧空态**

```vue
<section v-if="selected" class="right">
  <!-- 现有详情不变；过滤隐藏选中时仍显示 -->
</section>
<section v-else class="right muted">
  <template v-if="loading">加载中…</template>
  <template v-else-if="!symbols.length">暂无笔记标的</template>
  <template v-else>选择或打开一只股票</template>
</section>
```

- [ ] **Step 5: 样式**

参考 Feed：

```css
.filter {
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 0.5rem;
  color: var(--text);
  padding: 8px 10px;
  width: 100%;
}
.empty,
.hint {
  margin: 4px 0 0;
  font-size: 0.85rem;
}
```

- [ ] **Step 6: 前端构建自检**

```bash
cd frontend && npm run build
```

Expected: 成功。

- [ ] **Step 7: Commit**

```bash
git add frontend/src/views/NotesView.vue
git commit -m "$(cat <<'EOF'
feat(notes): 侧栏按代码/备忘过滤并区分空态

对齐 Feed 过滤体验；无标的/无匹配/加载中可区分。
EOF
)"
```

---

### Task 2: smoke + roadmap + check.sh

**Files:**
- Modify: `docs/smoke-checklist.md`
- Modify: `docs/product-roadmap.md`

- [ ] **Step 1: smoke**

在现有 `/notes` 条附近增加：

```markdown
- [ ] `/notes` 有标的时可按代码/备忘过滤；无匹配见「无匹配标的」；无标的见「暂无笔记标的」与打开引导；加载中可见提示
```

- [ ] **Step 2: roadmap #31**

在近期待办末尾增加：

```markdown
31. ~~笔记侧栏过滤与空态~~（已完成 → [spec](./superpowers/specs/2026-08-13-notes-sidebar-filter-ux-design.md)）
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
docs: 记录笔记侧栏过滤空态完成

更新 smoke 与路线图 #31。
EOF
)"
```

---

## Spec coverage（自审）

| Spec | Task |
|------|------|
| displayedSymbols 过滤 | 1 |
| 空态三分 + loading | 1 |
| 保持 selected | 1 |
| smoke + roadmap | 2 |
| 不改 API | Global |

无 TBD。

---

# NSF SDD progress

- Task 1: done @ 4be432c (approved)
- Task 2: done @ 5f813cb (approved)
- Final review: APPROVED

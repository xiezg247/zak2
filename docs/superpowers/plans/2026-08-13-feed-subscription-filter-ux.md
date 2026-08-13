# Feed 左侧订阅过滤 UX Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `/feed` 左侧按订阅名/mid 过滤；无匹配见「无匹配订阅」；滤掉当前选中时保持 `subId`。

**Architecture:** 纯前端 `displayedSubs`（对齐 NotesView `displayedSymbols`、右侧已有 `displayedItems`）；「全部」始终可见；不改 Feed API / 右侧 #23 过滤。

**Tech Stack:** Vue 3 `computed` / `ref`。

**Spec:** `docs/superpowers/specs/2026-08-13-feed-subscription-filter-ux-design.md`

## Global Constraints

- 只改 `FeedView.vue` + smoke + roadmap（本 plan 两 task）
- 不改 Feed API；不改批量已读 / 页内强制同步 / 「仅启用」过滤
- 过滤框仅在 `subs.length > 0` 时显示
- 滤掉当前订阅时 **保持** `subId`（不自动清空）
- Commit 简体中文；不 push

---

### Task 1: FeedView 左侧订阅过滤

**Files:**
- Modify: `frontend/src/views/FeedView.vue`

**Interfaces:**
- Consumes: 现有 `subs` / `subId` / `load` / 右侧 `listFilter`·`displayedItems`
- Produces: `subFilter`、`displayedSubs`

- [ ] **Step 1: 状态与 computed**

在 `listFilter` / `unreadOnly` 附近增加：

```typescript
const subFilter = ref('')

const displayedSubs = computed(() => {
  const q = subFilter.value.trim().toLowerCase()
  if (!q) return subs.value
  return subs.value.filter((s) => {
    const name = (s.display_name || '').toLowerCase()
    const mid = (s.source_id || '').toLowerCase()
    return name.includes(q) || mid.includes(q)
  })
})
```

- [ ] **Step 2: 模板左侧**

在「全部」按钮之前插入过滤框与空态；`v-for` 改用 `displayedSubs`：

```vue
<input
  v-if="subs.length"
  v-model="subFilter"
  class="sub-filter"
  placeholder="过滤订阅名/mid"
/>
<button type="button" class="sub" :class="{ on: !subId }" @click="subId = ''">全部</button>
<p v-if="subs.length && !displayedSubs.length" class="muted tiny-text">无匹配订阅</p>
<div v-for="s in displayedSubs" :key="s.id" class="sub-row">
  <button type="button" class="sub" :class="{ on: subId === s.id }" @click="subId = s.id">
    {{ s.display_name || s.source_id }}
  </button>
  <button type="button" class="tiny" @click="toggleSub(s)">{{ s.enabled ? '开' : '关' }}</button>
  <button type="button" class="tiny danger" @click="removeSub(s)">删</button>
</div>
```

保留现有 `!subs.length && !loading` 的 `sub-hint`；不改右侧时间线模板。

- [ ] **Step 3: 样式**

```css
.sub-filter {
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 0.5rem;
  color: var(--text);
  padding: 8px 10px;
  width: 100%;
  box-sizing: border-box;
}
```

- [ ] **Step 4: 前端构建自检**

```bash
cd frontend && npm run build
```

Expected: 成功。

- [ ] **Step 5: Commit**

```bash
git add frontend/src/views/FeedView.vue
git commit -m "$(cat <<'EOF'
feat(feed): 左侧按订阅名/mid 过滤

对齐笔记侧栏；无匹配见提示；滤掉时保持 subId。
EOF
)"
```

---

### Task 2: smoke + roadmap + check.sh

**Files:**
- Modify: `docs/smoke-checklist.md`
- Modify: `docs/product-roadmap.md`

- [ ] **Step 1: smoke**

在现有 `/feed` 时间线过滤条附近增加：

```markdown
- [ ] `/feed` 有订阅时可按名/mid 过滤左侧列表；无匹配见「无匹配订阅」；「全部」始终可见；过滤隐藏当前选中时右侧仍按该订阅显示
```

- [ ] **Step 2: roadmap #35**

在近期待办末尾（#34 后）增加：

```markdown
35. ~~Feed 左侧订阅过滤~~（已完成 → [spec](./superpowers/specs/2026-08-13-feed-subscription-filter-ux-design.md)）
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
docs: 记录 Feed 左侧订阅过滤完成

更新 smoke 与路线图 #35。
EOF
)"
```

---

## Spec coverage（自审）

| Spec | Task |
|------|------|
| displayedSubs 过滤名/mid | 1 |
| 「全部」始终可见 | 1 |
| 无匹配「无匹配订阅」 | 1 |
| 保持 subId | 1（不写清空逻辑） |
| 不过右侧 #23 | Global / Task 1 明确不改 |
| smoke + roadmap #35 | 2 |
| 不改 API | Global |

无 TBD。

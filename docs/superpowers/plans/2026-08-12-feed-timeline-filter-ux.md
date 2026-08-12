# Feed 时间线过滤与空态 UX Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Feed 时间线支持标题/作者/摘要过滤与「仅未读」，并区分无订阅 / 无动态 / 无匹配空态。

**Architecture:** 纯前端 `displayedItems`（filter → unreadOnly）；无动态链 Ops；无订阅左侧轻引导。

**Tech Stack:** Vue 3、vue-router `RouterLink`

**Spec:** `docs/superpowers/specs/2026-08-12-feed-timeline-filter-ux-design.md`

## Global Constraints

- 只改 zak2；不改 Feed API / sync job
- 不做订阅名过滤、批量已读、页内强制同步
- commit message 简体中文：`<type>(<scope>): <简述>`

## File map

| 路径 | 职责 |
|------|------|
| `frontend/src/views/FeedView.vue` | 管道 + UI |
| `docs/smoke-checklist.md` / `product-roadmap.md` | 文档 |

---

### Task 1: FeedView displayedItems + 空态

**Files:**
- Modify: `frontend/src/views/FeedView.vue`

- [ ] **Step 1: 状态与 computed**

```typescript
const listFilter = ref('')
const unreadOnly = ref(false)

const displayedItems = computed(() => {
  const q = listFilter.value.trim().toLowerCase()
  let list = items.value
  if (q) {
    list = list.filter((it) => {
      const t = (it.title || '').toLowerCase()
      const a = (it.author_name || '').toLowerCase()
      const s = (it.summary || '').toLowerCase()
      return t.includes(q) || a.includes(q) || s.includes(q)
    })
  }
  if (unreadOnly.value) {
    list = list.filter((it) => !it.is_read)
  }
  return list
})
```

- [ ] **Step 2: 右侧模板**

在刷新按钮旁/下增加过滤条（有 items 时）：

```html
<section class="right">
  <div class="right-tools">
    <button class="ghost" type="button" :disabled="loading" @click="load">刷新</button>
    <div v-if="items.length" class="filter-row">
      <input v-model="listFilter" placeholder="过滤标题/作者" />
      <label class="unread-label">
        <input v-model="unreadOnly" type="checkbox" />
        仅未读
      </label>
    </div>
  </div>

  <p v-if="loading" class="muted">加载中…</p>
  <template v-else>
    <p v-if="!subs.length" class="empty muted">暂无订阅</p>
    <p v-else-if="!items.length" class="empty muted">
      暂无动态。可到 Ops 执行 sync_bilibili_feed。
      <RouterLink to="/ops" class="draft-link">去 Ops</RouterLink>
    </p>
    <p v-else-if="!displayedItems.length" class="empty muted">无匹配动态</p>
    <article
      v-for="item in displayedItems"
      :key="item.id"
      class="item"
      :class="{ unread: !item.is_read }"
      @click="openItem(item)"
    >
      <!-- 现有 meta / title / summary 不变 -->
    </article>
  </template>
</section>
```

去掉原单独的 `<p v-if="!items.length" class="empty">暂无动态</p>`，避免与新空态重复。

- [ ] **Step 3: 左侧无订阅引导**

在左侧表单区（添加 mid / 搜索下方或「全部」按钮前）：

```html
<p v-if="!subs.length && !loading" class="muted tiny-text sub-hint">
  先搜索关键词或填写 mid 添加订阅。
</p>
```

- [ ] **Step 4: 样式**

```css
.right-tools { display: grid; gap: 8px; }
.filter-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}
.filter-row input {
  background: var(--bg);
  border: 1px solid var(--border);
  color: var(--text);
  border-radius: 0.5rem;
  padding: 6px 10px;
  min-width: 140px;
  flex: 1;
}
.unread-label {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 0.85rem;
  color: var(--muted);
  white-space: nowrap;
}
.draft-link { color: var(--brand); margin-left: 4px; }
.sub-hint { margin: 0; }
```

- [ ] **Step 5: build**

```bash
cd frontend && npm run build
```

Expected: 成功

- [ ] **Step 6: Commit**

```bash
git add frontend/src/views/FeedView.vue
git commit -m "$(cat <<'EOF'
feat(feed): 时间线支持过滤未读与分层空态

纯前端 displayedItems；无动态可去 Ops 同步。
EOF
)"
```

---

### Task 2: 文档 + check.sh

**Files:**
- Modify: `docs/smoke-checklist.md`
- Modify: `docs/product-roadmap.md`

- [ ] **Step 1: smoke（§6，紧接现有 `/feed` 条）**

```markdown
- [ ] `/feed` 有动态时可按标题/作者过滤与「仅未读」；无匹配显示「无匹配动态」；无订阅/无动态空态可区分（无动态可见去 Ops）
```

- [ ] **Step 2: roadmap**

```markdown
23. ~~Feed 时间线过滤空态~~（已完成 → [spec](./superpowers/specs/2026-08-12-feed-timeline-filter-ux-design.md)）
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
docs: 记录 Feed 时间线过滤空态完成

更新 smoke 与路线图。
EOF
)"
```

---

## Spec coverage（自审）

| Spec | Task |
|------|------|
| filter + 仅未读 + 四分空态 + 左侧引导 | 1 |
| smoke / roadmap | 2 |

无 TBD。

# Feed「仅启用」订阅过滤 UX Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `/feed` 左侧可选「仅启用」过滤（默认关），与名/mid 文本过滤叠加；滤掉选中时保持 `subId`。

**Architecture:** 扩展现有 `displayedSubs` 管道：可选 `enabled` → `subFilter`；checkbox 对齐右侧「仅未读」。

**Tech Stack:** Vue 3 `ref` / `computed`。

**Spec:** `docs/superpowers/specs/2026-08-13-feed-enabled-only-filter-ux-design.md`

## Global Constraints

- 只改 `FeedView.vue` + smoke + roadmap（本 plan 两 task）
- 不改 Feed API；不改批量已读 / 页内同步 / 右侧时间线过滤
- `enabledOnly` 默认 `false`；滤掉时保持 `subId`
- Commit 简体中文；不 push

---

### Task 1: FeedView enabledOnly

**Files:**
- Modify: `frontend/src/views/FeedView.vue`

**Interfaces:**
- Consumes: 现有 `subs` / `subFilter` / `displayedSubs` / `subId`
- Produces: `enabledOnly`；更新后的 `displayedSubs`

- [ ] **Step 1: 状态与管道**

在 `subFilter` 旁增加，并替换 `displayedSubs`：

```typescript
const enabledOnly = ref(false)

const displayedSubs = computed(() => {
  let list = subs.value
  if (enabledOnly.value) {
    list = list.filter((s) => s.enabled)
  }
  const q = subFilter.value.trim().toLowerCase()
  if (!q) return list
  return list.filter((s) => {
    const name = (s.display_name || '').toLowerCase()
    const mid = (s.source_id || '').toLowerCase()
    return name.includes(q) || mid.includes(q)
  })
})
```

- [ ] **Step 2: 模板控件**

在 `sub-filter` 输入后、「全部」前增加（与 `v-if="subs.length"` 同条件区域）：

```vue
<label v-if="subs.length" class="enabled-label">
  <input v-model="enabledOnly" type="checkbox" />
  仅启用
</label>
```

（若希望与过滤框同一行，可用 flex 包一层；否则单独一行即可。保留现有空态「无匹配订阅」与 `v-for="displayedSubs"`。）

- [ ] **Step 3: 样式**

对齐右侧 unread-label：

```css
.enabled-label {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 0.85rem;
  color: var(--muted);
  white-space: nowrap;
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
feat(feed): 左侧「仅启用」过滤订阅

默认关；与名/mid 过滤叠加；滤掉时保持 subId。
EOF
)"
```

---

### Task 2: smoke + roadmap + check.sh

**Files:**
- Modify: `docs/smoke-checklist.md`
- Modify: `docs/product-roadmap.md`

- [ ] **Step 1: smoke**

在现有 `/feed` 左侧订阅过滤条附近增加：

```markdown
- [ ] `/feed` 可勾选「仅启用」隐藏已关订阅（默认关）；可与名/mid 过滤叠加；无匹配见「无匹配订阅」；滤掉当前选中时右侧仍按该订阅显示
```

- [ ] **Step 2: roadmap #37**

在近期待办末尾（#36 后）增加：

```markdown
37. ~~Feed「仅启用」订阅过滤~~（已完成 → [spec](./superpowers/specs/2026-08-13-feed-enabled-only-filter-ux-design.md)）
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
docs: 记录 Feed「仅启用」订阅过滤完成

更新 smoke 与路线图 #37。
EOF
)"
```

---

## Spec coverage（自审）

| Spec | Task |
|------|------|
| enabledOnly 默认 false | 1 |
| 管道 enabled → text | 1 |
| 保持 subId | 1（不写清空） |
| smoke + #37 | 2 |
| 不改 API | Global |

无 TBD。

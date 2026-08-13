# 笔记安全操作与研报 Tab 薄打磨 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 删流水 confirm；研报 Tab 轻过滤/空态链 AI；`/ai?symbol=` 预填投研代码。

**Architecture:** 纯前端；NotesView 对齐侧栏过滤模式；AiView 读 route query。

**Tech Stack:** Vue 3、vue-router `RouterLink` / `useRoute`。

**Spec:** `docs/superpowers/specs/2026-08-13-notes-safety-reports-ux-design.md`

## Global Constraints

- 不改 notes REST；不做移出侧栏
- 不自动 `runTeam`
- Commit 简体中文；不 push

---

### Task 1: NotesView + AiView

**Files:**
- Modify: `frontend/src/views/NotesView.vue`
- Modify: `frontend/src/views/AiView.vue`

- [ ] **Step 1: NotesView — confirm**

```typescript
async function removeEntry(id: number) {
  if (!window.confirm('确定删除这条流水？')) return
  await contentApi.deleteEntry(id)
  await loadDetail()
  await loadSymbols()
}
```

- [ ] **Step 2: NotesView — 研报过滤**

```typescript
import { RouterLink } from 'vue-router'
// 若已用 vue-router 其它 API，一并 import

const reportFilter = ref('')

const displayedReports = computed(() => {
  const q = reportFilter.value.trim().toLowerCase()
  if (!q) return reports.value
  return reports.value.filter((r) => {
    const t = (r.title || '').toLowerCase()
    const s = (r.summary || '').toLowerCase()
    return t.includes(q) || s.includes(q)
  })
})
```

模板研报区改为：

```vue
<template v-else>
  <p v-if="!reports.length" class="muted">
    暂无研报。
    <RouterLink :to="{ path: '/ai', query: { symbol: selected } }">去 AI 跑投研团队</RouterLink>
  </p>
  <template v-else>
    <input v-model="reportFilter" class="filter" placeholder="过滤标题/摘要" />
    <p v-if="!displayedReports.length" class="empty muted">无匹配研报</p>
    <button
      v-for="r in displayedReports"
      :key="r.id"
      type="button"
      class="report-item"
      :class="{ on: activeReport?.id === r.id }"
      @click="openReport(r.id)"
    >
      <!-- 现有标题/时间/摘要 -->
    </button>
  </template>
  <article v-if="activeReport" class="report-body">
    <!-- 现有详情；过滤隐藏列表项时若仍选中可保留展示 -->
  </article>
</template>
```

（`filter` / `empty` 样式可复用侧栏已有 class。）

- [ ] **Step 3: AiView — query 预填**

```typescript
import { useRoute, useRouter } from 'vue-router'

const route = useRoute()
// ...
onMounted(async () => {
  const s = String(route.query.symbol || '').trim()
  if (s) teamSymbol.value = s
  try {
    status.value = await aiApi.status()
    await refreshSessions()
    await loadMessages()
  } catch (e) {
    error.value = e instanceof Error ? e.message : '加载失败'
  }
})
```

- [ ] **Step 4: 构建**

```bash
cd frontend && npm run build
```

Expected: 成功。

- [ ] **Step 5: Commit**

```bash
git add frontend/src/views/NotesView.vue frontend/src/views/AiView.vue
git commit -m "$(cat <<'EOF'
feat(notes): 删流水确认与研报过滤空态链 AI

AiView 支持 ?symbol= 预填投研代码。
EOF
)"
```

---

### Task 2: smoke + roadmap + check.sh

**Files:**
- Modify: `docs/smoke-checklist.md`
- Modify: `docs/product-roadmap.md`

- [ ] **Step 1: smoke**

在 `/notes` 相关条附近增加：

```markdown
- [ ] `/notes` 删流水有 confirm；研报 Tab 可按标题/摘要过滤；无匹配见「无匹配研报」；无研报可「去 AI 跑投研团队」（带当前代码）；`/ai?symbol=` 打开后投研输入框预填该代码
```

- [ ] **Step 2: roadmap #32**

```markdown
32. ~~笔记安全操作与研报 Tab 薄打磨~~（已完成 → [spec](./superpowers/specs/2026-08-13-notes-safety-reports-ux-design.md)）
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
docs: 记录笔记安全操作与研报 Tab 薄打磨完成

更新 smoke 与路线图 #32。
EOF
)"
```

---

## Spec coverage（自审）

| Spec | Task |
|------|------|
| confirm | 1 |
| 研报过滤/空态/链 | 1 |
| AiView 预填 | 1 |
| smoke + #32 | 2 |
| 不自动 runTeam / 无移出 API | Global |

无 TBD。

---

# NSR SDD progress

- Task 1: done @ 3cfb2c2 (approved)
- Task 2: done @ 34211ca (approved)
- Final review: APPROVED

# 自选列表空态与日 K Ops 引导 UX Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `/watchlist` 列表空态文案对齐；详情日 K 区分加载/空/错并链「去 Ops 补全日 K」。

**Architecture:** 纯前端。对齐 MarketView #36 的 `barsLoading` + Ops 链模式。

**Tech Stack:** Vue 3 `ref`；`RouterLink`。

**Spec:** `docs/superpowers/specs/2026-08-13-watchlist-empty-bars-ops-ux-design.md`

## Global Constraints

- 只改 `WatchlistView.vue` + smoke + roadmap（本 plan 两 task）
- 不改 watchlist API；不改分组/列偏好/策略看盘
- 空自选不挂 Ops
- Commit 简体中文；不 push

---

### Task 1: WatchlistView 空态与日 K Ops

**Files:**
- Modify: `frontend/src/views/WatchlistView.vue`

- [ ] **Step 1: barsLoading + loadBars**

在 `barsError` 旁：

```typescript
const barsLoading = ref(false)
```

替换 `loadBars`：

```typescript
async function loadBars() {
  barsError.value = ''
  bars.value = []
  if (!selected.value) {
    barsLoading.value = false
    return
  }
  barsLoading.value = true
  try {
    const resp = await watchlistApi.bars(selected.value.vt_symbol, 'd', barLimit.value)
    bars.value = resp.bars
  } catch (e) {
    barsError.value = e instanceof Error ? e.message : '无 K 线'
  } finally {
    barsLoading.value = false
  }
}
```

- [ ] **Step 2: 列表空态文案**

将：

```vue
{{ items.length === 0 ? '自选为空，上方输入代码添加' : '无匹配结果' }}
```

改为：

```vue
{{ items.length === 0 ? '暂无自选标的，上方输入代码添加' : '无匹配标的' }}
```

- [ ] **Step 3: 详情日 K 模板**

在 chart-head /「选择左侧…」之后，将原 `barsError` + `v-if="bars.length"` 图表块改为（保留现有图表与迷你表结构）：

```vue
<template v-if="selected">
  <p v-if="barsLoading" class="muted">加载日 K…</p>
  <template v-else-if="barsError">
    <p class="err">
      {{ barsError }}
      <RouterLink to="/ops" class="draft-link">去 Ops 补全日 K</RouterLink>
    </p>
  </template>
  <template v-else-if="!bars.length">
    <p class="muted">
      暂无日 K
      <RouterLink to="/ops" class="draft-link">去 Ops 补全日 K</RouterLink>
    </p>
  </template>
  <template v-else>
    <!-- 现有 .chart + .table-wrap.mini 原样移入 -->
  </template>
</template>
```

（无 `selected` 时仍保留「选择左侧标的查看日 K」。）

- [ ] **Step 4: 样式**

若尚无 `.draft-link`：

```css
.draft-link {
  color: var(--brand);
  margin-left: 4px;
}
```

- [ ] **Step 5: 前端构建自检**

```bash
cd frontend && npm run build
```

Expected: 成功。

- [ ] **Step 6: Commit**

```bash
git add frontend/src/views/WatchlistView.vue
git commit -m "$(cat <<'EOF'
feat(watchlist): 列表空态文案与日 K 不足引导去 Ops

对齐市场页；区分加载/空/错，避免空成功无提示。
EOF
)"
```

---

### Task 2: smoke + roadmap + check.sh

**Files:**
- Modify: `docs/smoke-checklist.md`
- Modify: `docs/product-roadmap.md`

- [ ] **Step 1: smoke**

在 `/watchlist` 列表相关条附近增加：

```markdown
- [ ] `/watchlist` 无自选见「暂无自选标的」；过滤无匹配见「无匹配标的」；选中后日 K 加载中见「加载日 K…」，失败或空成功见「去 Ops 补全日 K」
```

- [ ] **Step 2: roadmap #41**

在 #40 后增加：

```markdown
41. ~~自选列表空态与日 K Ops 引导~~（已完成 → [spec](./superpowers/specs/2026-08-13-watchlist-empty-bars-ops-ux-design.md)）
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
docs: 记录自选列表空态与日 K Ops 引导完成

更新 smoke 与路线图 #41。
EOF
)"
```

---

## Spec coverage（自审）

| Spec | Task |
|------|------|
| 列表文案 | 1 |
| barsLoading + Ops | 1 |
| smoke + #41 | 2 |
| 不改 API | Global |

无 TBD。

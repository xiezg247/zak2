# 市场排行空态与日 K Ops 引导 UX Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `/market` 排行空态挂「去 Ops」；详情日 K 区分加载/空/错，空与错链「去 Ops 补全日 K」。

**Architecture:** 纯前端：复用 `.draft-link`；`barsLoading` 区分假加载；不改 API。

**Tech Stack:** Vue 3 `ref`；`RouterLink`（页内已用）。

**Spec:** `docs/superpowers/specs/2026-08-13-market-rank-bars-ops-ux-design.md`

## Global Constraints

- 只改 `MarketView.vue` + smoke + roadmap（本 plan 两 task）
- 不改 market / watchlist bars API；不改情绪阈值、排行过滤排序、加自选
- 不深链具体 Ops job
- Commit 简体中文；不 push

---

### Task 1: MarketView 空态与日 K Ops 链

**Files:**
- Modify: `frontend/src/views/MarketView.vue`

**Interfaces:**
- Consumes: 现有 `ranks` / `selected` / `bars` / `barsError` / `selectRank` / `onField`
- Produces: `barsLoading`；排行与日 K 空态 Ops 链

- [ ] **Step 1: 增加 barsLoading**

在 `barsError` 旁：

```typescript
const barsLoading = ref(false)
```

- [ ] **Step 2: 更新 selectRank / onField**

```typescript
async function selectRank(r: RankRow) {
  selected.value = r
  barsError.value = ''
  bars.value = []
  addMsg.value = ''
  barsLoading.value = true
  try {
    const resp = await watchlistApi.bars(r.vt_symbol, 'd', 90)
    bars.value = resp.bars
  } catch (e) {
    barsError.value = e instanceof Error ? e.message : '无 K 线'
  } finally {
    barsLoading.value = false
  }
}

async function onField() {
  error.value = ''
  selected.value = null
  bars.value = []
  barsError.value = ''
  barsLoading.value = false
  try {
    ranks.value = await marketApi.ranks(field.value, 50)
  } catch (e) {
    ranks.value = []
    error.value = e instanceof Error ? e.message : '排行加载失败'
  }
}
```

- [ ] **Step 3: 排行空态模板**

将：

```vue
<tr v-if="!ranks.length">
  <td colspan="6" class="empty">暂无排行（需 Redis 行情快照）</td>
</tr>
```

改为：

```vue
<tr v-if="!ranks.length">
  <td colspan="6" class="empty">
    暂无排行（需 Redis 行情快照）
    <RouterLink to="/ops" class="draft-link">去 Ops</RouterLink>
  </td>
</tr>
```

- [ ] **Step 4: 详情日 K 模板**

将详情内图表相关块改为：

```vue
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
<div v-else class="chart">
  <CandleChart :bars="bars" :height="240" />
</div>
```

（替换原 `barsError` / `bars.length` / `加载日 K…` 三行；`addMsg` 与按钮区不动。）

- [ ] **Step 5: 前端构建自检**

```bash
cd frontend && npm run build
```

Expected: 成功。

- [ ] **Step 6: Commit**

```bash
git add frontend/src/views/MarketView.vue
git commit -m "$(cat <<'EOF'
feat(market): 排行空态与日 K 不足引导去 Ops

区分日 K 加载/空/错，避免空成功假加载。
EOF
)"
```

---

### Task 2: smoke + roadmap + check.sh

**Files:**
- Modify: `docs/smoke-checklist.md`
- Modify: `docs/product-roadmap.md`

- [ ] **Step 1: smoke**

在现有 `/market` 排行过滤条附近增加：

```markdown
- [ ] `/market` 无排行时见「暂无排行」与「去 Ops」；选中标的日 K 加载中见「加载日 K…」，失败或空成功见「去 Ops 补全日 K」（不再假加载）
```

- [ ] **Step 2: roadmap #36**

在近期待办末尾（#35 后）增加：

```markdown
36. ~~市场排行空态与日 K Ops 引导~~（已完成 → [spec](./superpowers/specs/2026-08-13-market-rank-bars-ops-ux-design.md)）
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
docs: 记录市场排行空态与日 K Ops 引导完成

更新 smoke 与路线图 #36。
EOF
)"
```

---

## Spec coverage（自审）

| Spec | Task |
|------|------|
| 排行空态去 Ops | 1 |
| barsLoading + 空/错 Ops 链 | 1 |
| 不改 API / 过滤 / 情绪 | Global |
| smoke + roadmap #36 | 2 |

无 TBD。

# 板块空态 Ops 链与雷达共振过滤 UX Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `/sectors` 无数据空态挂「去 Ops」；`/radar` 共振侧栏按代码/名称过滤并区分无匹配空态。

**Architecture:** 纯前端。板块复用 `RouterLink` + `.draft-link`；雷达扩展 `displayedResonance`（对齐市场排行过滤）。

**Tech Stack:** Vue 3 `ref` / `computed`。

**Spec:** `docs/superpowers/specs/2026-08-13-sector-ops-radar-resonance-filter-ux-design.md`

## Global Constraints

- 只改 `SectorView.vue` + `RadarView.vue` + smoke + roadmap（本 plan 两 task）
- 不改 sector / radar API；不改卡片网格、权重、展望、板块表过滤排序逻辑
- 「无匹配板块」不挂 Ops
- Commit 简体中文；不 push

---

### Task 1: SectorView Ops 链 + RadarView 共振过滤

**Files:**
- Modify: `frontend/src/views/SectorView.vue`
- Modify: `frontend/src/views/RadarView.vue`

**Interfaces:**
- Consumes: 现有 `rows` / `resonance` / 侧栏模板
- Produces: 板块 Ops 链；`resonanceFilter`、`displayedResonance`

- [ ] **Step 1: SectorView 空态 + 样式**

将：

```vue
<p v-else-if="!error && !rows.length" class="muted empty-hint">
  暂无板块资金。可先到 Ops 执行 sync_sector_flow_daily。
</p>
```

改为：

```vue
<p v-else-if="!error && !rows.length" class="muted empty-hint">
  暂无板块资金。可先到 Ops 执行 sync_sector_flow_daily。
  <RouterLink to="/ops" class="draft-link">去 Ops</RouterLink>
</p>
```

在 `<style scoped>` 增加（若尚无）：

```css
.draft-link {
  color: var(--brand);
  margin-left: 4px;
}
```

（`RouterLink` 与页内「← 市场」一致，通常无需手写 import。）

- [ ] **Step 2: RadarView 状态与 computed**

在 `resonance` 相关 ref 附近：

```typescript
const resonanceFilter = ref('')

const displayedResonance = computed(() => {
  const q = resonanceFilter.value.trim().toLowerCase()
  if (!q) return resonance.value
  return resonance.value.filter((e) => {
    const vt = (e.vt_symbol || '').toLowerCase()
    const name = (e.name || '').toLowerCase()
    return vt.includes(q) || name.includes(q)
  })
})
```

- [ ] **Step 3: RadarView 侧栏模板**

在 Hub 按钮之后、`side-list` 内：过滤框 + `v-for` 改用 `displayedResonance` + 空态分支。推荐结构：

```vue
<input
  v-if="resonance.length"
  v-model="resonanceFilter"
  class="side-filter"
  placeholder="过滤代码/名称"
/>
<div class="side-list">
  <div v-for="(e, i) in displayedResonance" :key="e.vt_symbol" class="side-row">
    <!-- 现有 side-row 内容不变；rank 用 i + 1 -->
  </div>
  <p v-if="!resonance.length" class="muted empty-side">
    暂无共振标的（需至少 2 张卡片命中同一标的；可调权重后刷新）
  </p>
  <p v-else-if="!displayedResonance.length" class="muted empty-side">无匹配共振</p>
</div>
```

（把原「仅 `!resonance.length`」空态改为上表两分支；过滤框可放在 `side-list` 外、Hub 按钮下。）

- [ ] **Step 4: RadarView 样式**

```css
.side-filter {
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 0.5rem;
  color: var(--text);
  padding: 6px 10px;
  width: 100%;
  box-sizing: border-box;
}
```

- [ ] **Step 5: 前端构建自检**

```bash
cd frontend && npm run build
```

Expected: 成功。

- [ ] **Step 6: Commit**

```bash
git add frontend/src/views/SectorView.vue frontend/src/views/RadarView.vue
git commit -m "$(cat <<'EOF'
feat(ui): 板块空态去 Ops 与雷达共振侧栏过滤

对齐市场 Ops 引导；共振按代码/名称过滤并区分无匹配。
EOF
)"
```

---

### Task 2: smoke + roadmap + check.sh

**Files:**
- Modify: `docs/smoke-checklist.md`
- Modify: `docs/product-roadmap.md`

- [ ] **Step 1: smoke**

在 `/sectors` 过滤条附近增加或改写验收（可新增一行）：

```markdown
- [ ] `/sectors` 无数据时见空态文案与「去 Ops」；有数据过滤无匹配仍见「无匹配板块」（不挂 Ops）
```

在 `/radar` 共振相关条附近增加：

```markdown
- [ ] `/radar` 有共振时可按代码/名称过滤侧栏；无匹配见「无匹配共振」；真无共振文案仍说明需 ≥2 卡命中
```

- [ ] **Step 2: roadmap #38**

在 #37 后增加：

```markdown
38. ~~板块空态 Ops 与雷达共振过滤~~（已完成 → [spec](./superpowers/specs/2026-08-13-sector-ops-radar-resonance-filter-ux-design.md)）
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
docs: 记录板块 Ops 与雷达共振过滤完成

更新 smoke 与路线图 #38。
EOF
)"
```

---

## Spec coverage（自审）

| Spec | Task |
|------|------|
| 板块去 Ops | 1 |
| 共振过滤代码/名称 | 1 |
| 无匹配共振 vs 真无 | 1 |
| smoke + #38 | 2 |
| 不改 API | Global |

无 TBD。

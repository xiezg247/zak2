# 雷达首屏 / 空态 UX Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 雷达页加载可见「加载中…」；无卡片空态引导 Ops 预热；共振空态文案更明确。

**Architecture:** 纯前端改 `RadarView.vue` 三处文案/条件渲染；复用现有 `draft-link` 样式链到 `/ops`。

**Tech Stack:** Vue 3、Vue Router

**Spec:** `docs/superpowers/specs/2026-08-12-radar-empty-loading-ux-design.md`

## Global Constraints

- 只改 zak2；不改雷达 API / warm job / 展望
- 空态条件：`!loading && !error && cards.length===0`
- commit message 简体中文：`<type>(<scope>): <简述>`

## File map

| 路径 | 职责 |
|------|------|
| `frontend/src/views/RadarView.vue` | 加载/空态 UI |
| `docs/smoke-checklist.md` / `product-roadmap.md` | 文档 |

---

### Task 1: RadarView UX

**Files:**
- Modify: `frontend/src/views/RadarView.vue`

确认已 `import { RouterLink } from 'vue-router'`（草案区已用则无需再引）。

- [ ] **Step 1: 工具条加载提示**

在刷新按钮后：

```html
<span v-if="loading" class="muted">加载中…</span>
```

- [ ] **Step 2: 主区无卡片空态**

在 `.main` 内、`grid` 之前（或 `v-if` 包住 grid）：

```html
<p v-if="!loading && !error && !cards.length" class="muted empty-main">
  暂无雷达卡片。可点刷新，或于 Ops 手动执行 warm_radar_card_snapshots 预热缓存。
  <RouterLink to="/ops" class="draft-link">去 Ops</RouterLink>
</p>
<div v-else class="grid">
  <!-- 现有 card buttons 不变 -->
</div>
```

注意：`detail` section 仍在 `v-if="active"`，无卡片时不显示即可。

- [ ] **Step 3: 共振空态**

将：

```html
<p v-if="!resonance.length" class="muted empty-side">暂无共振（刷新雷达卡片后再试）</p>
```

改为：

```html
<p v-if="!resonance.length" class="muted empty-side">
  暂无共振标的（需至少 2 张卡片命中同一标的；可调权重后刷新）
</p>
```

- [ ] **Step 4: 样式（可选最小）**

```css
.empty-main {
  padding: 24px 8px;
  line-height: 1.6;
}
```

- [ ] **Step 5: build**

```bash
cd frontend && npm run build
```

Expected: 成功

- [ ] **Step 6: Commit**

```bash
git add frontend/src/views/RadarView.vue
git commit -m "$(cat <<'EOF'
fix(radar): 补齐首屏加载与空态提示

无卡片引导 Ops 预热；共振空态文案更明确。
EOF
)"
```

---

### Task 2: 文档 + check.sh

**Files:**
- Modify: `docs/smoke-checklist.md`
- Modify: `docs/product-roadmap.md`

- [ ] **Step 1: smoke（§5 市场·板块·雷达）**

```markdown
- [ ] `/radar` 刷新时可见「加载中…」；无卡片时见空态并可「去 Ops」；无共振时侧栏文案说明需 ≥2 卡命中
```

- [ ] **Step 2: roadmap**

```markdown
16. ~~雷达首屏空态 UX~~（已完成 → [spec](./superpowers/specs/2026-08-12-radar-empty-loading-ux-design.md)）
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
docs: 记录雷达首屏空态 UX 完成

更新 smoke 与路线图。
EOF
)"
```

---

## Spec coverage（自审）

| Spec | Task |
|------|------|
| 加载 / 无卡片 / 共振空态 | 1 |
| smoke / roadmap | 2 |

无 TBD。

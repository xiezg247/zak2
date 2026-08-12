# 市场 ↔ 板块页眉互链 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 市场页与板块页工具条增加无 query 的 RouterLink 互跳。

**Architecture:** 两页 toolbar 各加一条 `RouterLink` + `.cross-link` 样式；不改 AppShell / API。

**Tech Stack:** Vue 3、vue-router

**Spec:** `docs/superpowers/specs/2026-08-12-market-sector-crosslink-design.md`

## Global Constraints

- 只改 zak2；无 query；不改 AppShell / ranks / sectorFlow
- 不改排行过滤、情绪周期、板块表既有逻辑
- commit message 简体中文：`<type>(<scope>): <简述>`

## File map

| 路径 | 职责 |
|------|------|
| `frontend/src/views/MarketView.vue` | 「板块资金 →」 |
| `frontend/src/views/SectorView.vue` | 「← 市场」 |
| `docs/smoke-checklist.md` / `product-roadmap.md` | 文档 |

---

### Task 1: 两页 toolbar 互链

**Files:**
- Modify: `frontend/src/views/MarketView.vue`
- Modify: `frontend/src/views/SectorView.vue`

- [ ] **Step 1: MarketView**

在 `.toolbar` → `.actions` 内（刷新按钮旁）增加：

```html
<RouterLink to="/sectors" class="cross-link">板块资金 →</RouterLink>
```

样式（scoped，若已有 `.draft-link` 可近似复用或并列）：

```css
.cross-link {
  color: var(--brand);
  text-decoration: none;
  font-size: 0.85rem;
  white-space: nowrap;
}
.cross-link:hover {
  text-decoration: underline;
}
```

（`RouterLink` 与情绪空态一致，可不显式 import。）

- [ ] **Step 2: SectorView**

在 `.toolbar` 末尾增加链接；若 toolbar 仅为 flex 左对齐，可包一层右侧：

```html
<div class="toolbar">
  <!-- 现有 tabs / select 不变 -->
  <RouterLink to="/market" class="cross-link toolbar-cross">← 市场</RouterLink>
</div>
```

可选：`.toolbar { justify-content: space-between; }` 或 `margin-left: auto` 把链推到右侧：

```css
.toolbar-cross {
  margin-left: auto;
}
.cross-link {
  color: var(--brand);
  text-decoration: none;
  font-size: 0.85rem;
  white-space: nowrap;
  align-self: center;
}
.cross-link:hover {
  text-decoration: underline;
}
```

勿破坏现有 tabs/select 换行布局。

- [ ] **Step 3: build**

```bash
cd frontend && npm run build
```

Expected: 成功

- [ ] **Step 4: Commit**

```bash
git add frontend/src/views/MarketView.vue frontend/src/views/SectorView.vue
git commit -m "$(cat <<'EOF'
feat(ui): 市场与板块页工具条互链

页内一键跳转 /market ↔ /sectors，无 query。
EOF
)"
```

---

### Task 2: 文档 + check.sh

**Files:**
- Modify: `docs/smoke-checklist.md`
- Modify: `docs/product-roadmap.md`

- [ ] **Step 1: smoke（§5）**

```markdown
- [ ] `/market` 工具条「板块资金 →」可进 `/sectors`；`/sectors`「← 市场」可回 `/market`
```

- [ ] **Step 2: roadmap**

```markdown
22. ~~市场与板块页眉互链~~（已完成 → [spec](./superpowers/specs/2026-08-12-market-sector-crosslink-design.md)）
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
docs: 记录市场与板块页眉互链完成

更新 smoke 与路线图。
EOF
)"
```

---

## Spec coverage（自审）

| Spec | Task |
|------|------|
| 双向 RouterLink | 1 |
| smoke / roadmap | 2 |

无 TBD。

# 雷达展望读路径薄壳 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 雷达页增加可折叠「展望」说明区（暂不可用 + 去 Ops），不读 cache、不新增 API。

**Architecture:** 纯前端 `RadarView.vue` 面板；复用 `tiny-btn` / `draft-link` 模式。

**Tech Stack:** Vue 3、Vue Router

**Spec:** `docs/superpowers/specs/2026-08-12-radar-horizon-shell-ux-design.md`

## Global Constraints

- 只改 zak2；不实现管线；不读/写 horizon cache；不新增 GET
- 默认折叠；不伪造展望行
- commit message 简体中文：`<type>(<scope>): <简述>`

## File map

| 路径 | 职责 |
|------|------|
| `frontend/src/views/RadarView.vue` | 展望面板 |
| `docs/smoke-checklist.md` / `product-roadmap.md` | 文档 |

---

### Task 1: RadarView 展望面板

**Files:**
- Modify: `frontend/src/views/RadarView.vue`

- [ ] **Step 1: 状态**

靠近其它 ref：

```typescript
const horizonOpen = ref(false)
```

- [ ] **Step 2: 模板**

在 `draftMsg` 段落之后、`.body` 之前插入：

```html
<div class="horizon-block">
  <div class="horizon-head">
    <strong>展望</strong>
    <span class="muted">暂不可用</span>
    <button type="button" class="ghost tiny-btn" @click="horizonOpen = !horizonOpen">
      {{ horizonOpen ? '收起' : '展开' }}
    </button>
  </div>
  <div v-if="horizonOpen" class="horizon-panel muted">
    <p>
      zak2 尚未接入雷达展望扫描管线（horizon / predict），当前无展望数据可读。
      Ops 中的 scan_horizon_outlook 为可跑占位（恒 skipped），待管线落地后再展示结果。
    </p>
    <RouterLink to="/ops" class="draft-link">去 Ops</RouterLink>
  </div>
</div>
```

- [ ] **Step 3: 样式**

对齐权重/行业头：

```css
.horizon-block {
  margin: 0 0 12px;
}
.horizon-head {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
.horizon-panel {
  margin-top: 8px;
  padding: 10px 12px;
  line-height: 1.6;
}
```

确认已有 `.tiny-btn` / `.draft-link`（空态刀已用）。

- [ ] **Step 4: build**

```bash
cd frontend && npm run build
```

Expected: 成功

- [ ] **Step 5: Commit**

```bash
git add frontend/src/views/RadarView.vue
git commit -m "$(cat <<'EOF'
feat(radar): 增加展望暂不可用说明面板

折叠展示管线未接入与 Ops 占位引导。
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
- [ ] `/radar` 可见「展望 · 暂不可用」可展开；文案说明管线未接入与 scan_horizon_outlook 占位；可「去 Ops」
```

- [ ] **Step 2: roadmap**

```markdown
17. ~~雷达展望读路径薄壳~~（已完成 → [spec](./superpowers/specs/2026-08-12-radar-horizon-shell-ux-design.md)）
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
docs: 记录雷达展望读路径薄壳完成

更新 smoke 与路线图。
EOF
)"
```

---

## Spec coverage（自审）

| Spec | Task |
|------|------|
| 折叠面板 + 文案 + Ops 链接 | 1 |
| smoke / roadmap | 2 |

无 TBD。

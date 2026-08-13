# 雷达详情反馈清空与操作钮样式 UX Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 换卡/`load` 清空 `detailMsg`；详情操作钮改用 `.tiny-btn`。

**Architecture:** 纯前端小修 #39 Minor；复用现有 `.tiny-btn`。

**Tech Stack:** Vue 3 `watch`。

**Spec:** `docs/superpowers/specs/2026-08-13-radar-detail-msg-btn-polish-ux-design.md`

## Global Constraints

- 只改 `RadarView.vue` + smoke + roadmap（本 plan 两 task）
- 不改 API / 加自选逻辑 / 文本 `.tiny` 语义
- Commit 简体中文；不 push

---

### Task 1: RadarView 清空与 class

**Files:**
- Modify: `frontend/src/views/RadarView.vue`

- [ ] **Step 1: load 清空 detailMsg**

在 `load()` 内 `sideMsg.value = ''` 旁增加：

```typescript
detailMsg.value = ''
```

- [ ] **Step 2: watch activeId**

在现有 `watch`/`computed` 区域增加（确保已从 `vue` import `watch`）：

```typescript
watch(activeId, () => {
  detailMsg.value = ''
})
```

- [ ] **Step 3: 详情钮 class**

将详情操作三钮的 `class="tiny"` 改为 `class="tiny-btn"`（三处）。

- [ ] **Step 4: 前端构建自检**

```bash
cd frontend && npm run build
```

Expected: 成功。

- [ ] **Step 5: Commit**

```bash
git add frontend/src/views/RadarView.vue
git commit -m "$(cat <<'EOF'
fix(radar): 换卡清空详情反馈并统一操作钮样式

修 #39 Minor：detailMsg 随 activeId/load 清空；详情钮用 tiny-btn。
EOF
)"
```

---

### Task 2: smoke + roadmap + check.sh

**Files:**
- Modify: `docs/smoke-checklist.md`
- Modify: `docs/product-roadmap.md`

- [ ] **Step 1: smoke**

在 #39 详情行操作条附近增加或改写补充：

```markdown
- [ ] `/radar` 详情加自选反馈后切换卡片，详情区反馈清空；详情操作钮样式与侧栏小按钮一致
```

- [ ] **Step 2: roadmap #40**

在 #39 后增加：

```markdown
40. ~~雷达详情反馈清空与操作钮样式~~（已完成 → [spec](./superpowers/specs/2026-08-13-radar-detail-msg-btn-polish-ux-design.md)）
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
docs: 记录雷达详情反馈清空与操作钮样式完成

更新 smoke 与路线图 #40。
EOF
)"
```

---

## Spec coverage（自审）

| Spec | Task |
|------|------|
| load + watch 清 detailMsg | 1 |
| tiny-btn | 1 |
| smoke + #40 | 2 |

无 TBD。

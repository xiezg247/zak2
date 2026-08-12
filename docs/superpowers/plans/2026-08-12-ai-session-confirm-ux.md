# AI 会话过滤与确认卡 UX Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** AI 页支持会话标题过滤、未配置 LLM 提示、确认卡参数折叠与处理中文案。

**Architecture:** 纯前端改 `AiView.vue`；不改 AI / 确认 API。

**Tech Stack:** Vue 3

**Spec:** `docs/superpowers/specs/2026-08-12-ai-session-confirm-ux-design.md`

## Global Constraints

- 只改 zak2；不改 `/api/v1/ai/*`
- 不做消息 Markdown、团队分析大改、会话重命名
- commit message 简体中文：`<type>(<scope>): <简述>`

## File map

| 路径 | 职责 |
|------|------|
| `frontend/src/views/AiView.vue` | 过滤、空态、确认卡、样式 |
| `docs/smoke-checklist.md` / `product-roadmap.md` | 文档 |

---

### Task 1: AiView 会话过滤 + 确认卡分层

**Files:**
- Modify: `frontend/src/views/AiView.vue`

- [ ] **Step 1: 状态与 computed**

```typescript
const sessionFilter = ref('')
/** proposal_id -> args 是否展开 */
const argsOpen = ref<Record<string, boolean>>({})

function sessionTitle(s: { title: string }): string {
  return (s.title || '').trim() || '未命名'
}

const displayedSessions = computed(() => {
  const q = sessionFilter.value.trim().toLowerCase()
  if (!q) return sessions.value
  return sessions.value.filter((s) => sessionTitle(s).toLowerCase().includes(q))
})

function toggleArgs(id: string) {
  argsOpen.value = { ...argsOpen.value, [id]: !argsOpen.value[id] }
}

function hasArgs(p: ConfirmProposal): boolean {
  return Object.keys(p.args || {}).length > 0
}

function formatArgs(p: ConfirmProposal): string {
  try {
    return JSON.stringify(p.args || {}, null, 2)
  } catch {
    return String(p.args)
  }
}
```

（确保已 `import type { ConfirmProposal }` 或从现有 import 取类型。）

- [ ] **Step 2: 顶栏未配置提示**

在 `<p v-if="error">` 附近：

```html
<p v-if="status && !status.configured" class="warn-banner muted">
  未配置 LLM_API_KEY，对话与团队分析不可用。
</p>
```

- [ ] **Step 3: 左侧会话列表**

在会话 `v-for` 前：

```html
<div v-if="sessions.length" class="session-filter">
  <input v-model="sessionFilter" placeholder="过滤会话" />
</div>
<p v-if="!sessions.length" class="muted tiny sess-empty">暂无会话，点上方新对话</p>
<p v-else-if="!displayedSessions.length" class="muted tiny sess-empty">无匹配会话</p>
<button
  v-for="s in displayedSessions"
  :key="s.id"
  ...
>
  <span>{{ sessionTitle(s) }}</span>
  ...
</button>
```

- [ ] **Step 4: 确认卡**

在 `confirm-body` 后、`detail` 前插入：

```html
<button
  v-if="hasArgs(p)"
  type="button"
  class="ghost tiny-btn"
  @click="toggleArgs(p.proposal_id)"
>
  {{ argsOpen[p.proposal_id] ? '收起参数' : '参数' }}
</button>
<pre v-if="hasArgs(p) && argsOpen[p.proposal_id]" class="args-pre">{{ formatArgs(p) }}</pre>
```

确认按钮：

```html
{{ actingId === p.proposal_id ? '处理中…' : '确认' }}
```

- [ ] **Step 5: 样式**

```css
.warn-banner {
  margin: 0 0 8px;
  padding: 8px 10px;
  border: 1px solid var(--border);
  border-radius: 0.5rem;
  background: var(--surface-muted, var(--bg-elevated));
}
.session-filter input {
  width: 100%;
  box-sizing: border-box;
  background: var(--bg);
  border: 1px solid var(--border);
  color: var(--text);
  border-radius: 0.5rem;
  padding: 6px 10px;
  font-size: 0.85rem;
}
.sess-empty { margin: 4px 0; }
.args-pre {
  margin: 6px 0 0;
  padding: 8px;
  font-size: 0.75rem;
  overflow: auto;
  max-height: 160px;
  background: var(--bg);
  border-radius: 0.4rem;
  border: 1px solid var(--border);
}
.tiny-btn {
  justify-self: start;
  margin-top: 6px;
  font-size: 0.8rem;
  padding: 4px 8px;
}
```

（若已有 `.tiny` / `.ghost` 可复用 class，避免冲突。）

- [ ] **Step 6: build**

```bash
cd frontend && npm run build
```

Expected: 成功

- [ ] **Step 7: Commit**

```bash
git add frontend/src/views/AiView.vue
git commit -m "$(cat <<'EOF'
feat(ai): 会话过滤与确认卡参数折叠

未配置 LLM 顶栏提示；确认中显示处理中。
EOF
)"
```

---

### Task 2: 文档 + check.sh

**Files:**
- Modify: `docs/smoke-checklist.md`
- Modify: `docs/product-roadmap.md`

- [ ] **Step 1: smoke（§6，紧接现有 `/ai` 条）**

```markdown
- [ ] `/ai` 可按标题过滤会话；无会话/无匹配空态可区分；未配置 LLM 时见顶栏提示；确认卡可展开参数且确认中显示「处理中…」
```

- [ ] **Step 2: roadmap**

```markdown
24. ~~AI 会话过滤与确认卡 UX~~（已完成 → [spec](./superpowers/specs/2026-08-12-ai-session-confirm-ux-design.md)）
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
docs: 记录 AI 会话过滤与确认卡 UX 完成

更新 smoke 与路线图。
EOF
)"
```

---

## Spec coverage（自审）

| Spec | Task |
|------|------|
| 会话过滤/空态 + 未配置提示 + 确认卡 | 1 |
| smoke / roadmap | 2 |

无 TBD。

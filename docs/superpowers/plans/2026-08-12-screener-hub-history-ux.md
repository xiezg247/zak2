# 选股 Hub 运行历史打磨 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Hub 运行历史空态/高亮/加载错误反馈；diff 可展开新增/移除代码并写入结果过滤。

**Architecture:** 纯前端增强 `ScreenerHubView.vue`：`historyBusy`/`runBusy`/`historyErr`/`showDiffDetail`；复用 `.hist.on`；不改 runs API。

**Tech Stack:** Vue 3

**Spec:** `docs/superpowers/specs/2026-08-12-screener-hub-history-ux-design.md`

## Global Constraints

- 只改 zak2；不改后端 / DELETE run / diff 计算
- loadHistory 失败保留旧列表
- openRun 成功清 `resultFilter`；kept 不展开 chips
- commit message 简体中文：`<type>(<scope>): <简述>`

## File map

| 路径 | 职责 |
|------|------|
| `frontend/src/views/ScreenerHubView.vue` | 历史 UX + diff 展开 |
| `docs/smoke-checklist.md` / `product-roadmap.md` | 文档 |

---

### Task 1: ScreenerHubView 历史 + diff UX

**Files:**
- Modify: `frontend/src/views/ScreenerHubView.vue`

- [ ] **Step 1: 增加状态**

靠近 `history` ref：

```typescript
const historyBusy = ref(false)
const runBusy = ref(false)
const historyErr = ref('')
const showDiffDetail = ref(false)
```

- [ ] **Step 2: 改 loadHistory / openRun**

```typescript
async function loadHistory() {
  historyBusy.value = true
  historyErr.value = ''
  try {
    history.value = await screenerApi.runs()
  } catch (e) {
    historyErr.value = e instanceof Error ? e.message : '加载历史失败'
  } finally {
    historyBusy.value = false
  }
}

async function openRun(id: string) {
  runBusy.value = true
  error.value = ''
  try {
    current.value = await screenerApi.run(id)
    resultFilter.value = ''
    showDiffDetail.value = false
  } catch (e) {
    error.value = e instanceof Error ? e.message : '打开运行记录失败'
  } finally {
    runBusy.value = false
  }
}

function applyDiffFilter(vt: string) {
  resultFilter.value = vt
}

function toggleDiffDetail() {
  showDiffDetail.value = !showDiffDetail.value
}
```

确认 `pollJob` 成功路径仍 `await loadHistory()`（已有）。

- [ ] **Step 3: 历史区模板**

替换历史 block 为：

```html
<div class="block history">
  <div class="history-head">
    <h3>运行历史</h3>
    <button
      type="button"
      class="ghost tiny-btn"
      :disabled="historyBusy"
      @click="loadHistory"
    >
      {{ historyBusy ? '刷新中…' : '刷新' }}
    </button>
  </div>
  <p v-if="historyErr" class="err">{{ historyErr }}</p>
  <p v-else-if="!historyBusy && !history.length" class="muted">
    暂无运行记录，点上方「运行」生成
  </p>
  <button
    v-for="h in history"
    :key="h.id"
    type="button"
    class="hist"
    :class="{ on: current?.id === h.id }"
    :disabled="runBusy"
    @click="openRun(h.id)"
  >
    <span>{{ h.condition }}</span>
    <span class="muted">{{ h.row_count }} 只 · {{ h.created_at }}</span>
  </button>
</div>
```

（`tiny-btn` / `history-head` 若无样式，对齐行业白名单 `industry-head`：flex 横排。）

- [ ] **Step 4: diff 展开**

替换现有 diff 块：

```html
<div v-if="diff" class="diff">
  <div class="diff-summary">
    <span>新增 {{ diff.added.length }}</span>
    <span>移除 {{ diff.removed.length }}</span>
    <span>保留 {{ diff.kept.length }}</span>
    <button type="button" class="link" @click="toggleDiffDetail">
      {{ showDiffDetail ? '收起' : '详情' }}
    </button>
  </div>
  <div v-if="showDiffDetail" class="diff-detail">
    <div v-if="diff.added.length" class="diff-group">
      <strong>新增</strong>
      <div class="chips">
        <button
          v-for="vt in diff.added"
          :key="'a-' + vt"
          type="button"
          class="chip-link mono"
          @click="applyDiffFilter(vt)"
        >
          {{ vt }}
        </button>
      </div>
    </div>
    <div v-if="diff.removed.length" class="diff-group">
      <strong>移除</strong>
      <div class="chips">
        <button
          v-for="vt in diff.removed"
          :key="'r-' + vt"
          type="button"
          class="chip-link mono"
          @click="applyDiffFilter(vt)"
        >
          {{ vt }}
        </button>
      </div>
    </div>
    <p
      v-if="!diff.added.length && !diff.removed.length"
      class="muted tip"
    >
      无新增或移除
    </p>
  </div>
</div>
```

复用页面已有 `.chips` / `.chip-link` / `.link`；必要时补最小 CSS：

```css
.history-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
.diff-summary {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
}
.diff-detail {
  margin-top: 8px;
  display: grid;
  gap: 8px;
}
```

- [ ] **Step 5: build**

```bash
cd frontend && npm run build
```

Expected: 成功

- [ ] **Step 6: Commit**

```bash
git add frontend/src/views/ScreenerHubView.vue
git commit -m "$(cat <<'EOF'
feat(screener): 打磨 Hub 运行历史与 diff 详情

空态/高亮/刷新与错误反馈；diff 可展开并写入过滤。
EOF
)"
```

---

### Task 2: 文档 + check.sh

**Files:**
- Modify: `docs/smoke-checklist.md`
- Modify: `docs/product-roadmap.md`

- [ ] **Step 1: smoke（§4）**

```markdown
- [ ] Hub 运行历史：空态可读；刷新可用；打开某条后该条高亮；有 diff 时可展开新增/移除代码并点选写入结果过滤
```

- [ ] **Step 2: roadmap**

```markdown
14. ~~选股 Hub 运行历史打磨~~（已完成 → [spec](./superpowers/specs/2026-08-12-screener-hub-history-ux-design.md)）
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
docs: 记录选股 Hub 运行历史打磨完成

更新 smoke 与路线图。
EOF
)"
```

---

## Spec coverage（自审）

| Spec | Task |
|------|------|
| 空态/高亮/busy/err/刷新/openRun 清过滤 | 1 |
| diff 展开 + 过滤 | 1 |
| smoke / roadmap | 2 |

无 TBD。

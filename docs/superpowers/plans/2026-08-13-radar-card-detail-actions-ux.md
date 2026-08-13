# 雷达卡片详情行操作 UX Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `/radar` 卡片详情表对有 vt 的行提供加自选、在自选打开、去笔记；详情区独立反馈。

**Architecture:** 纯前端。抽出 `rowVt`；`addWatchTo` 写指定 msg ref；详情操作列三钮。不改 API。

**Tech Stack:** Vue 3；现有 `watchlistApi` / `router`。

**Spec:** `docs/superpowers/specs/2026-08-13-radar-card-detail-actions-ux-design.md`

## Global Constraints

- 只改 `RadarView.vue` + smoke + roadmap（本 plan 两 task）
- 不改 radar API；不改卡片网格、共振过滤、展望
- 无 vt 行操作列「—」；详情用 `detailMsg`
- Commit 简体中文；不 push

---

### Task 1: RadarView 详情行操作

**Files:**
- Modify: `frontend/src/views/RadarView.vue`

**Interfaces:**
- Consumes: 现有 `addWatch` / `actingVt` / `rowVtKeys` / `active.rows`
- Produces: `rowVt`、`detailMsg`、`addWatchTo`、操作列、跳转 helpers

- [ ] **Step 1: 状态与 helpers**

在 script 中（`sideMsg` 旁）增加：

```typescript
const detailMsg = ref('')

function rowVt(row: Record<string, unknown>): string {
  for (const k of ['vt_symbol', 'tf_symbol', 'symbol'] as const) {
    const v = String(row[k] || '').trim()
    if (v) return v
  }
  return ''
}

function openInWatchlist(vt: string) {
  void router.push({ path: '/watchlist', query: { symbol: vt } })
}

function openInNotes(vt: string) {
  void router.push({ path: '/notes', query: { symbol: vt } })
}
```

将现有 `addWatch` 重构为共享实现（行为不变：侧栏仍写 `sideMsg`）：

```typescript
async function addWatchTo(
  vt: string,
  name: string | undefined,
  msg: { value: string },
) {
  if (!vt || actingVt.value) return
  actingVt.value = vt
  msg.value = ''
  try {
    await watchlistApi.add(vt, name || '')
    msg.value = `已加入自选 ${vt}`
  } catch (e) {
    msg.value = e instanceof Error ? e.message : '加自选失败'
  } finally {
    actingVt.value = ''
  }
}

async function addWatch(vt: string, name?: string) {
  await addWatchTo(vt, name, sideMsg)
}

async function addWatchFromDetail(vt: string, name?: string) {
  await addWatchTo(vt, name, detailMsg)
}
```

- [ ] **Step 2: 详情模板**

在详情 `h2` / subtitle 后：

```vue
<p v-if="detailMsg" class="detail-msg">{{ detailMsg }}</p>
```

表头增加「操作」；空态 `colspan="4"`；行内：

```vue
<th>操作</th>
<!-- ... -->
<td>
  <template v-if="rowVt(row)">
    <button
      type="button"
      class="tiny"
      :disabled="actingVt === rowVt(row)"
      @click="addWatchFromDetail(rowVt(row), String(row.name || ''))"
    >
      加自选
    </button>
    <button type="button" class="tiny" @click="openInWatchlist(rowVt(row))">在自选打开</button>
    <button type="button" class="tiny" @click="openInNotes(rowVt(row))">去笔记</button>
  </template>
  <template v-else>—</template>
</td>
```

（实现时可先 `const vt = rowVt(row)` 避免三次调用——在模板里用内联或包一层小组件均可；**允许**在 `v-for` 内三次调用 `rowVt`，或改用 computed map。推荐模板内局部：若不便，三次调用可接受。）

为减少重复，可用：

```vue
<tr v-for="(row, i) in active.rows" :key="i">
  <!-- ... -->
  <td class="row-actions">
    <template v-if="rowVt(row) as vt /* 不行 */">
```

Vue 模板不支持 as。用两次调用即可，或：

```vue
<td class="row-actions">
  <template v-if="rowVt(row)">
    <button ... @click="addWatchFromDetail(rowVt(row), String(row.name || ''))">加自选</button>
    ...
  </template>
  <span v-else>—</span>
</td>
```

- [ ] **Step 3: 样式**

```css
.detail-msg {
  margin: 0 0 8px;
  font-size: 0.85rem;
  color: var(--muted);
}
.row-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  white-space: nowrap;
}
.tiny {
  /* 若尚无：对齐 Feed/侧栏 tiny 按钮 */
  background: transparent;
  border: 1px solid var(--border);
  color: var(--muted);
  border-radius: 0.5rem;
  padding: 2px 8px;
  font-size: 0.8rem;
}
```

（若文件已有 `.tiny`，只加 `.detail-msg` / `.row-actions`。）

- [ ] **Step 4: 前端构建自检**

```bash
cd frontend && npm run build
```

Expected: 成功。

- [ ] **Step 5: Commit**

```bash
git add frontend/src/views/RadarView.vue
git commit -m "$(cat <<'EOF'
feat(radar): 卡片详情行支持加自选与跳转

有 vt 时提供加自选、在自选打开、去笔记；详情区独立反馈。
EOF
)"
```

---

### Task 2: smoke + roadmap + check.sh

**Files:**
- Modify: `docs/smoke-checklist.md`
- Modify: `docs/product-roadmap.md`

- [ ] **Step 1: smoke**

在 `/radar` 相关条附近增加：

```markdown
- [ ] `/radar` 卡片详情有 vt 的行可见「加自选」「在自选打开」「去笔记」；加自选反馈在详情区；无 vt 行操作列为「—」
```

- [ ] **Step 2: roadmap #39**

在 #38 后增加：

```markdown
39. ~~雷达卡片详情行操作~~（已完成 → [spec](./superpowers/specs/2026-08-13-radar-card-detail-actions-ux-design.md)）
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
docs: 记录雷达卡片详情行操作完成

更新 smoke 与路线图 #39。
EOF
)"
```

---

## Spec coverage（自审）

| Spec | Task |
|------|------|
| 操作列三钮 | 1 |
| detailMsg | 1 |
| 无 vt → — | 1 |
| smoke + #39 | 2 |
| 不改 API | Global |

无 TBD。

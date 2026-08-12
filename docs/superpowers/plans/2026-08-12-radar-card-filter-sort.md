# 雷达卡片筛选排序 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 雷达卡片网格支持 source chips、标题/来源过滤、按标题/行数排序。

**Architecture:** 纯前端 `displayedCards` 管道（source → query → sort）；`watch` 同步 `activeId`；有卡才显示过滤条。

**Tech Stack:** Vue 3

**Spec:** `docs/superpowers/specs/2026-08-12-radar-card-filter-sort-design.md`

## Global Constraints

- 只改 zak2；不改雷达 API / 共振 / 展望
- 真无卡空态与「无匹配卡片」分支分开
- commit message 简体中文：`<type>(<scope>): <简述>`

## File map

| 路径 | 职责 |
|------|------|
| `frontend/src/views/RadarView.vue` | 管道 + UI |
| `docs/smoke-checklist.md` / `product-roadmap.md` | 文档 |

---

### Task 1: RadarView displayedCards + UI

**Files:**
- Modify: `frontend/src/views/RadarView.vue`

- [ ] **Step 1: 状态与 computed**

靠近 `cards` / `activeId`：

```typescript
const cardFilter = ref('')
const sourceChip = ref('')
const cardSortKey = ref<'title' | 'rows' | null>(null)
const cardSortDir = ref<'asc' | 'desc'>('desc')

const sourceOptions = computed(() => {
  const set = new Set<string>()
  for (const c of cards.value) {
    const s = (c.source || '').trim()
    if (s) set.add(s)
  }
  return [...set].sort((a, b) => a.localeCompare(b, 'zh'))
})

function cmpCardNullable(
  a: number | string | null | undefined,
  b: number | string | null | undefined,
  dir: 'asc' | 'desc',
): number {
  const aM = a == null || a === '' || (typeof a === 'number' && Number.isNaN(a))
  const bM = b == null || b === '' || (typeof b === 'number' && Number.isNaN(b))
  if (aM && bM) return 0
  if (aM) return 1
  if (bM) return -1
  if (typeof a === 'number' && typeof b === 'number') {
    const d = a - b
    return dir === 'asc' ? d : -d
  }
  const d = String(a).localeCompare(String(b), 'zh')
  return dir === 'asc' ? d : -d
}

function toggleCardSort(key: 'title' | 'rows') {
  if (cardSortKey.value === key) {
    cardSortDir.value = cardSortDir.value === 'asc' ? 'desc' : 'asc'
  } else {
    cardSortKey.value = key
    cardSortDir.value = 'desc'
  }
}

function clearCardSort() {
  cardSortKey.value = null
}

function cardSortMark(key: 'title' | 'rows'): string {
  if (cardSortKey.value !== key) return ''
  return cardSortDir.value === 'asc' ? ' ▲' : ' ▼'
}

const displayedCards = computed(() => {
  const q = cardFilter.value.trim().toLowerCase()
  let list = cards.value
  if (sourceChip.value) {
    list = list.filter((c) => (c.source || '').trim() === sourceChip.value)
  }
  if (q) {
    list = list.filter((c) => {
      const t = (c.title || '').toLowerCase()
      const sub = (c.subtitle || '').toLowerCase()
      const src = (c.source || '').toLowerCase()
      return t.includes(q) || sub.includes(q) || src.includes(q)
    })
  }
  const key = cardSortKey.value
  if (!key) return list
  const dir = cardSortDir.value
  return [...list].sort((a, b) => {
    if (key === 'rows') return cmpCardNullable(a.rows.length, b.rows.length, dir)
    return cmpCardNullable(a.title || '', b.title || '', dir)
  })
})
```

- [ ] **Step 2: watch active**

```typescript
watch(displayedCards, (list) => {
  if (!list.length) {
    if (cards.value.length) activeId.value = ''
    return
  }
  if (!list.some((c) => c.card_id === activeId.value)) {
    activeId.value = list[0].card_id
  }
})
```

（真无卡时由现有 empty-main 处理；勿在 `!cards.length` 时强行清 active 导致闪烁——仅当有 cards 但 displayed 空时清空。）

- [ ] **Step 3: 模板**

有 `cards.length` 时（`v-else` 分支内 grid 前）加过滤条；grid 改 `displayedCards`；无匹配空态：

```html
<template v-if="!loading && !error && !cards.length">
  <!-- 现有 empty-main 保持 -->
</template>
<template v-else>
  <div v-if="cards.length" class="card-tools">
    <div class="chips">
      <button type="button" class="chip" :class="{ on: !sourceChip }" @click="sourceChip = ''">全部</button>
      <button
        v-for="s in sourceOptions"
        :key="s"
        type="button"
        class="chip"
        :class="{ on: sourceChip === s }"
        @click="sourceChip = s"
      >
        {{ s }}
      </button>
    </div>
    <div class="row filter-row">
      <input v-model="cardFilter" placeholder="过滤标题/来源" />
      <button type="button" class="ghost" :class="{ on: !cardSortKey }" @click="clearCardSort">默认序</button>
      <button type="button" class="ghost" @click="toggleCardSort('title')">标题{{ cardSortMark('title') }}</button>
      <button type="button" class="ghost" @click="toggleCardSort('rows')">行数{{ cardSortMark('rows') }}</button>
    </div>
  </div>
  <p v-if="cards.length && !displayedCards.length" class="muted empty-main">无匹配卡片</p>
  <div v-else class="grid">
    <button v-for="c in displayedCards" ...>
      <!-- 现有 card 内容 -->
    </button>
  </div>
  <!-- detail 仍 v-if="active" -->
</template>
```

按现有结构微调：原 `v-if empty` / `v-else grid` 改为上述，避免破坏 detail。

- [ ] **Step 4: 样式**

复用或补：

```css
.card-tools { display: grid; gap: 10px; margin-bottom: 12px; }
.chips { display: flex; flex-wrap: wrap; gap: 8px; }
.chip {
  border: 1px solid var(--border, #ccc);
  background: transparent;
  padding: 4px 10px;
  cursor: pointer;
  border-radius: 4px;
}
.chip.on { border-color: var(--accent, #333); font-weight: 600; }
.filter-row { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
```

（若文件已有 `.chips` 用于其它用途，注意冲突；雷达页可能无 chips——可命名 `source-chips`。）

确认 `import { watch } from 'vue'`（现仅 computed/onMounted/ref 则补上）。

- [ ] **Step 5: build**

```bash
cd frontend && npm run build
```

Expected: 成功

- [ ] **Step 6: Commit**

```bash
git add frontend/src/views/RadarView.vue
git commit -m "$(cat <<'EOF'
feat(radar): 卡片支持来源筛选与排序过滤

纯前端 displayedCards；无匹配与真无卡空态分离。
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
- [ ] `/radar` 有卡片时可按 source chip / 标题过滤与标题·行数排序；无匹配显示「无匹配卡片」；真无卡仍见 Ops 空态
```

- [ ] **Step 2: roadmap**

```markdown
18. ~~雷达卡片筛选排序~~（已完成 → [spec](./superpowers/specs/2026-08-12-radar-card-filter-sort-design.md)）
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
docs: 记录雷达卡片筛选排序完成

更新 smoke 与路线图。
EOF
)"
```

---

## Spec coverage（自审）

| Spec | Task |
|------|------|
| chips + 过滤 + 排序 + active 同步 | 1 |
| smoke / roadmap | 2 |

无 TBD。

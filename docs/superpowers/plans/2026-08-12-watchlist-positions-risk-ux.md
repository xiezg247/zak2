# 自选持仓与风控 UX 打磨 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 风控 tip 去桌面；持仓表展示现价/市值；计划外摘要可展开芯片并选中标的。

**Architecture:** 纯前端：补 `market_value` 类型；`WatchlistView` 扩列 + `showOffPlanChips` 切换；文档更新。不改后端。

**Tech Stack:** Vue 3、TypeScript

**Spec:** `docs/superpowers/specs/2026-08-12-watchlist-positions-risk-ux-design.md`

## Global Constraints

- 只改 zak2；不改后端 / strategy_board / CRUD API
- 风控 tip 新文案不得含「桌面」
- 计划外仅 UI 展开 chips + `selectVt`；不做后端重排
- 录入反馈不新增滚动定位
- commit message 简体中文：`<type>(<scope>): <简述>`

## File map

| 路径 | 职责 |
|------|------|
| `frontend/src/api/watchlist.ts` | `market_value` 类型 |
| `frontend/src/views/WatchlistView.vue` | tip、列、计划外 chips |
| `docs/smoke-checklist.md` / `product-roadmap.md` | 文档 |

---

### Task 1: 类型 + WatchlistView UX

**Files:**
- Modify: `frontend/src/api/watchlist.ts`
- Modify: `frontend/src/views/WatchlistView.vue`

**Interfaces:**
- Consumes: 既有 `risk_summary.off_plan_*`、`StrategyPositionRow.last_price`、board `market_value`
- Produces: 列展示 + 计划外 toggle

- [ ] **Step 1: 类型**

`StrategyPositionRow` 增加：

```typescript
market_value: number | null
```

- [ ] **Step 2: script 状态与 helper**

在 `WatchlistView.vue` script（靠近 risk 相关 ref）：

```typescript
const showOffPlanChips = ref(false)

function formatMarketValue(v: number | null | undefined): string {
  if (v == null || Number.isNaN(v)) return '—'
  return v.toLocaleString()
}

function toggleOffPlanChips() {
  if (!riskSummary.value || riskSummary.value.off_plan_count <= 0) return
  showOffPlanChips.value = !showOffPlanChips.value
}
```

- [ ] **Step 3: 风控 tip + 计划外摘要**

将 risk-summary 中「计划外」改为可点（count>0），并在下方展开 chips；tip 替换：

```html
<div class="risk-summary muted" v-if="riskSummary">
  <span>实际仓位 {{ formatPctRatio(riskSummary.actual_position_pct) }}</span>
  <button
    v-if="riskSummary.off_plan_count > 0"
    type="button"
    class="link"
    @click="toggleOffPlanChips"
  >
    计划外 {{ riskSummary.off_plan_count }}
  </button>
  <span v-else>计划外 {{ riskSummary.off_plan_count }}</span>
  <span>计划日 {{ riskSummary.active_plan_date || '—' }}</span>
</div>
<div v-if="showOffPlanChips && riskSummary?.off_plan_symbols?.length" class="chips">
  <span v-for="vt in riskSummary.off_plan_symbols" :key="vt" class="chip-tag">
    <button type="button" class="chip-link mono" @click="selectVt(vt)">{{ vt }}</button>
  </span>
</div>
<p class="muted tip">止损按百分数填写（如 5 = 5%）；浮亏警戒为负数（如 -5）。写入用户风控偏好。</p>
```

（保留原有 risk form / 保存按钮结构；仅替换 tip 与 summary 计划外部分。若现有 tip 在保存按钮后，就地替换文案即可。）

样式：若 `.link` 在 risk-summary 内需微调（`border:0; background:transparent; padding:0; cursor:pointer`），优先复用页面已有 `.link` / `.chip-link`。

- [ ] **Step 4: 持仓表列**

表头与行增加现价、市值（在数量与浮盈%之间）；空行 colspan=10：

```html
<th>现价</th>
<th>市值</th>
<!-- ... -->
<td>{{ row.last_price != null ? row.last_price.toFixed(2) : '—' }}</td>
<td>{{ formatMarketValue(row.market_value) }}</td>
```

- [ ] **Step 5: build**

```bash
cd frontend && npm run build
```

Expected: 成功

- [ ] **Step 6: Commit**

```bash
git add frontend/src/api/watchlist.ts frontend/src/views/WatchlistView.vue
git commit -m "$(cat <<'EOF'
feat(watchlist): 持仓现价市值与计划外芯片

风控 tip 去桌面；计划外可展开选中。
EOF
)"
```

---

### Task 2: 文档 + check.sh

**Files:**
- Modify: `docs/smoke-checklist.md`
- Modify: `docs/product-roadmap.md`

- [ ] **Step 1: smoke**

自选节增加：

```markdown
- [ ] `/watchlist` 风控 tip 无「桌面」；持仓区可见现价/市值；计划外>0 时可展开芯片并点选标的
```

- [ ] **Step 2: roadmap**

```markdown
12. ~~持仓与风控 UX 打磨~~（已完成 → [spec](./superpowers/specs/2026-08-12-watchlist-positions-risk-ux-design.md)）
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
docs: 记录持仓与风控 UX 打磨完成

更新 smoke 与路线图。
EOF
)"
```

---

## Spec coverage（自审）

| Spec | Task |
|------|------|
| market_value 类型 + 列 + tip + 计划外 | 1 |
| smoke / roadmap + check | 2 |

无 TBD。

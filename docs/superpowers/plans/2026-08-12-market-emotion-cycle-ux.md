# 市场情绪周期展示 UX Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 市场页情绪周期卡片分层（阶段/可否新开为主）、inputs 默认可折叠、无周期 Ops 空态、卡片快捷展开阈值。

**Architecture:** 纯前端改 `MarketView.vue` 模板与少量状态；不改 emotion/thresholds API。

**Tech Stack:** Vue 3、vue-router `RouterLink`

**Spec:** `docs/superpowers/specs/2026-08-12-market-emotion-cycle-ux-design.md`

## Global Constraints

- 只改 zak2；不改 `build_emotion_cycle` / thresholds API
- 阈值区仍仅在有 `emotion_cycle` 时显示
- 不改排行过滤排序逻辑
- commit message 简体中文：`<type>(<scope>): <简述>`

## File map

| 路径 | 职责 |
|------|------|
| `frontend/src/views/MarketView.vue` | 分层 UI + 空态 + 阈值快捷 |
| `docs/smoke-checklist.md` / `product-roadmap.md` | 文档 |

空态链接对齐：`RadarView.vue` 的 `RouterLink to="/ops"`。

---

### Task 1: MarketView 情绪卡片分层 + 空态

**Files:**
- Modify: `frontend/src/views/MarketView.vue`

- [ ] **Step 1: 状态与 helpers**

```typescript
import { RouterLink } from 'vue-router' // 若模板用 RouterLink 且未自动可用则显式导入；Vue SFC 通常已全局/无需——按项目其它页写法（RadarView 直接用即可）

const cycleInputsOpen = ref(false)
const thresholdsSectionEl = ref<HTMLElement | null>(null)

function openThresholdsFromCard() {
  thresholdsOpen.value = true
  void nextTick(() => {
    thresholdsSectionEl.value?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
  })
}
```

从 `vue` 增加导入 `nextTick`（若尚未导入）。

- [ ] **Step 2: 有周期卡片模板**

替换现有 `v-if="overview.emotion_cycle"` 卡片内容为分层结构，例如：

```html
<div class="card" v-if="overview.emotion_cycle">
  <div class="k">情绪周期</div>
  <div class="cycle-head">
    <div class="v">{{ overview.emotion_cycle.stage_label }}</div>
    <span
      class="cycle-gate"
      :class="overview.emotion_cycle.allow_new_positions ? 'ok' : 'warn'"
    >
      {{ overview.emotion_cycle.allow_new_positions ? '可新开' : '不宜新开' }}
    </span>
  </div>
  <div class="s muted">
    仓位建议 {{ posPct(overview.emotion_cycle) }}
    <template v-if="overview.emotion_cycle.allowed_mode_labels.length">
      · {{ overview.emotion_cycle.allowed_mode_labels.join('/') }}
    </template>
  </div>
  <div
    class="s warn"
    v-for="(w, i) in overview.emotion_cycle.warnings"
    :key="i"
  >
    {{ w }}
  </div>
  <div class="cycle-actions">
    <button
      type="button"
      class="ghost tiny-btn"
      @click="cycleInputsOpen = !cycleInputsOpen"
    >
      {{ cycleInputsOpen ? '收起明细' : '明细' }}
    </button>
    <button type="button" class="ghost tiny-btn" @click="openThresholdsFromCard">
      阈值
    </button>
  </div>
  <div class="s muted" v-if="cycleInputsOpen && overview.emotion_cycle.inputs">
    涨停 {{ overview.emotion_cycle.inputs.limit_up_count ?? '—' }} · 跌停
    {{ overview.emotion_cycle.inputs.limit_down_count ?? '—' }} · 最高板
    {{ overview.emotion_cycle.inputs.max_limit_times ?? '—' }}
    <template v-if="overview.emotion_cycle.inputs.fear_greed_index != null">
      · 恐贪≈{{ overview.emotion_cycle.inputs.fear_greed_index }}
    </template>
    <template v-if="overview.emotion_cycle.inputs.index_above_ma5 === true"> · 站上MA5</template>
    <template v-else-if="overview.emotion_cycle.inputs.index_above_ma5 === false"> · 跌破MA5</template>
  </div>
</div>
```

- [ ] **Step 3: 无周期空态**

```html
<div class="card" v-else>
  <div class="k">情绪周期</div>
  <div class="v muted">暂无数据</div>
  <p class="s muted empty-cycle-hint">
    可到 Ops 执行 warm_market_summary 预热。
    <RouterLink to="/ops" class="draft-link">去 Ops</RouterLink>
  </p>
</div>
```

- [ ] **Step 4: 阈值区 ref**

```html
<section
  v-if="overview?.emotion_cycle"
  ref="thresholdsSectionEl"
  class="thresholds-section"
>
  ...现有内容不变...
</section>
```

- [ ] **Step 5: 样式**

```css
.cycle-head {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 8px;
  margin-top: 4px;
}
.cycle-head .v { margin-top: 0; }
.cycle-gate {
  font-size: 0.85rem;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 0.4rem;
  border: 1px solid var(--border);
}
.cycle-gate.ok {
  color: var(--ok);
  border-color: var(--ok);
}
.cycle-gate.warn {
  color: var(--danger);
  border-color: var(--danger);
}
.cycle-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 8px;
}
.draft-link {
  color: var(--brand);
  margin-left: 4px;
}
.empty-cycle-hint { margin: 6px 0 0; }
```

（若已有 `.draft-link` / `.tiny-btn` 则复用。）

- [ ] **Step 6: build**

```bash
cd frontend && npm run build
```

Expected: 成功

- [ ] **Step 7: Commit**

```bash
git add frontend/src/views/MarketView.vue
git commit -m "$(cat <<'EOF'
feat(market): 情绪周期卡片分层与空态 Ops 提示

主视觉突出可否新开；明细默认折叠；卡片可快捷展开阈值。
EOF
)"
```

---

### Task 2: 文档 + check.sh

**Files:**
- Modify: `docs/smoke-checklist.md`
- Modify: `docs/product-roadmap.md`

- [ ] **Step 1: smoke（§5，紧接情绪/排行相关条）**

```markdown
- [ ] `/market` 情绪周期：有数据时阶段与可否新开醒目、明细可折叠、卡片「阈值」可展开判定区；无数据时见 warm_market_summary 提示与「去 Ops」
```

- [ ] **Step 2: roadmap**

```markdown
21. ~~市场情绪周期展示 UX~~（已完成 → [spec](./superpowers/specs/2026-08-12-market-emotion-cycle-ux-design.md)）
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
docs: 记录市场情绪周期展示 UX 完成

更新 smoke 与路线图。
EOF
)"
```

---

## Spec coverage（自审）

| Spec | Task |
|------|------|
| 分层 + 明细折叠 + 阈值快捷 + 空态 Ops | 1 |
| smoke / roadmap | 2 |

无 TBD。

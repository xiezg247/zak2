# 看板顶部工具条实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 看板顶部重构为一条三段式工具条（模式 tabs | 风控输入 | 操作按钮），移除大标题、meta 与实际仓位展示。

**Architecture:** 纯前端改动 `frontend/src/views/BoardView.vue`。删除 `summary-grid` 风控卡与 `.board-head`，合并为单条 `.topbar`；移除 `riskSummary` computed 与 `formatPctRatio`；风控提示/结果信息放工具条下方一行。正文两列结构不变。

**Tech Stack:** Vue 3 + TypeScript + Vite

## Global Constraints

- 前端 TypeScript 必须通过 `vue-tsc` 与 `eslint`（`npm run build` 通过）
- prettier 格式通过（`npm run format:check`）
- 不加后端改动；不改信号/持仓表结构与模式切换业务逻辑
- 移除不再引用的 `riskSummary`、`formatPctRatio`（避免 unused lint）
- commit message 用简体中文，格式 `<type>(<scope>): <简述>`

---

### Task 1: 顶部工具条重构

**Files:**
- Modify: `frontend/src/views/BoardView.vue`

**Interfaces:**
- Consumes: `signalMode` / `signalForm.*`（`riskForm.total_capital/stop_loss_pct/caution_float_pct`）/ `prefsReady` / `riskSaving` / `riskError` / `riskMsg` / `enqueueing` / `saveTradingRisk` / `setSignalMode` / `openAlignedBacktest` / `enqueueAlignedBacktest` / `refreshBoard`（全部既有）
- Produces: 无新接口（纯模板/样式重组）

- [ ] **Step 1: script 区移除不再使用的风险指标**

在 `frontend/src/views/BoardView.vue` 中：

1. 删除 `const riskSummary = computed(() => board.value?.risk_summary ?? null)`
2. 删除 `formatPctRatio` 函数

保留 `formatMarketValue`（持仓表仍使用）。

- [ ] **Step 2: 模板区移除风控卡与旧工具条，替换为单条 topbar**

删除整个 `.summary-grid` 块（含 `.risk-card` section）与 `.board-head` 块（含 h2、meta、mode-tabs、三个操作按钮），替换为：

```html
<div class="topbar">
  <div class="mode-tabs">
    <button
      type="button"
      class="ghost"
      :class="{ on: signalMode === 'heuristic_v2' }"
      @click="setSignalMode('heuristic_v2')"
    >
      启发式确认
    </button>
    <button
      type="button"
      class="ghost"
      :class="{ on: signalMode === 'double_ma' }"
      @click="setSignalMode('double_ma')"
    >
      回测双均线
    </button>
    <button
      type="button"
      class="ghost"
      :class="{ on: signalMode === 'trend_ma' }"
      @click="setSignalMode('trend_ma')"
    >
      趋势均线
    </button>
  </div>

  <div class="risk-form">
    <label>
      总资金
      <input
        v-model="riskForm.total_capital"
        type="number"
        step="1000"
        min="0"
        placeholder="可选"
        :disabled="!prefsReady || riskSaving"
      />
    </label>
    <label>
      止损%
      <input
        v-model="riskForm.stop_loss_pct"
        type="number"
        step="0.1"
        min="0.1"
        max="50"
        :disabled="!prefsReady || riskSaving"
      />
    </label>
    <label>
      浮亏警戒
      <input
        v-model="riskForm.caution_float_pct"
        type="number"
        step="0.5"
        max="-0.1"
        :disabled="!prefsReady || riskSaving"
      />
    </label>
    <button
      type="button"
      class="primary"
      :disabled="!prefsReady || riskSaving"
      @click="saveTradingRisk"
    >
      {{ riskSaving ? '保存中…' : '保存风控' }}
    </button>
  </div>

  <div class="actions">
    <button type="button" class="ghost" @click="openAlignedBacktest()">同参回测</button>
    <button
      type="button"
      class="ghost"
      :disabled="enqueueing"
      @click="enqueueAlignedBacktest()"
    >
      {{ enqueueing ? '入队中…' : '入队回测' }}
    </button>
    <button type="button" class="ghost" @click="refreshBoard()">刷新看板</button>
  </div>
</div>

<div class="topbar-feedback">
  <p v-if="!prefsReady" class="muted">加载风控偏好…</p>
  <p v-else-if="riskError" class="err">{{ riskError }}</p>
  <p v-else-if="riskMsg" class="muted">{{ riskMsg }}</p>
  <p class="muted tip">止损按百分数（如 5 = 5%）；浮亏警戒为负数（如 -5）。</p>
</div>
```

（原 `board?.note` 提示与 `boardError` 显示保持在其下方原位置。）

- [ ] **Step 3: 样式区调整**

在 `<style scoped>` 中：

1. 删除 `.summary-grid` 与 `.risk-grid` 规则（不再使用；`.pos-grid` 仍被持仓表单使用，保留）
2. 新增 `.topbar`、`.risk-form`、`.topbar-feedback` 样式：

```css
.topbar {
  display: flex;
  align-items: flex-end;
  gap: 16px;
  flex-wrap: wrap;
  padding: 10px 12px;
  border: 1px solid var(--line);
  border-radius: 0.75rem;
  background: var(--surface);
  box-shadow: var(--shadow-card);
}
.mode-tabs {
  display: inline-flex;
  gap: 4px;
}
.risk-form {
  display: flex;
  align-items: flex-end;
  gap: 10px;
  flex-wrap: wrap;
}
.risk-form label {
  display: grid;
  gap: 4px;
  font-size: 0.78rem;
  color: var(--muted);
}
.risk-form input {
  width: 110px;
  background: var(--bg-elevated);
  border: 1px solid var(--border);
  border-radius: 0.5rem;
  color: var(--text);
  padding: 6px 8px;
}
.risk-form input:focus {
  border-color: var(--brand);
  box-shadow: 0 0 0 3px rgba(230, 100, 50, 0.15);
  outline: none;
}
.topbar .actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-left: auto;
}
.topbar-feedback {
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
}
.topbar-feedback p {
  margin: 0;
}
```

3. 删除媒体查询中 `.summary-grid`（若已不存在则不动）：

原媒体查询应改为：

```css
@media (max-width: 900px) {
  .board-grid,
  .pos-grid {
    grid-template-columns: 1fr;
  }
}
```

- [ ] **Step 4: 构建验证**

Run: `cd frontend && npm run build`
Expected: `vue-tsc` + `vite build` 通过（确认无 unused 报错）

Run: `cd frontend && npm run lint:check && npm run format:check`
Expected: 通过（`BoardView.vue` 不在 format 问题列表）

- [ ] **Step 5: 提交**

```bash
git add frontend/src/views/BoardView.vue
git commit -m "feat(ui): 看板顶部重构为紧凑工具条

风控、模式切换与操作按钮合一为工具条，移除大标题与 meta 行。"
```

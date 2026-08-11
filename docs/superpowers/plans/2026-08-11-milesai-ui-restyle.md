# MilesAI 浅色 UI 重设计 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 zak2 前端从深色终端风改为 MilesAI 同系浅色橙品牌，保留左侧栏布局，壳层与登录页优先，业务页轻量色值适配。

**Architecture:** 在 `style.css` 建立 MilesAI 对齐的 CSS 变量与全局组件类，并保留旧变量别名以降低各 view 一次性改动量；重写 `AppShell` / `LoginView` 样式；定点替换各 view 中硬编码深色 hex；图表仅调轴/网格/背景可读性。

**Tech Stack:** Vue 3、Vite、纯 CSS（不引入 Tailwind）

**Spec:** `docs/superpowers/specs/2026-08-11-milesai-ui-restyle-design.md`

## Global Constraints

- 只改 `frontend/`；不改后端、不改路由/API/业务逻辑
- 不引入 Tailwind / UnoCSS；不迁 Next.js
- 保留左侧栏 + 主区；导航顺序不变
- 品牌橙 `#E66432`；涨跌红绿独立，不混用 brand
- 业务页不大改 DOM/交互；仅色值与对比度
- commit message 简体中文：`<type>(<scope>): <简述>`

## File map

| 路径 | 职责 |
|------|------|
| `frontend/src/style.css` | 新 token、旧变量别名、全局 `.card` / `.btn-*` / `.input-field` / 表格 |
| `frontend/src/components/AppShell.vue` | 侧栏 + 顶栏浅色样式与激活态 |
| `frontend/src/views/LoginView.vue` | 浅色登录卡 |
| `frontend/src/views/*.vue` | 硬编码深色 hex → token / 浅色可读值 |
| `frontend/src/components/CandleChart.vue` | 浅色背景下的轴/网格（涨跌色保留） |
| `frontend/src/App.vue` | 若依赖旧 muted 色，确认仍可读 |

---

### Task 1: 全局 Token 与组件类

**Files:**
- Modify: `frontend/src/style.css`
- Test: 目视 + `cd frontend && npm run build`

**Interfaces:**
- Produces: `:root` 新 token（`--brand` 等）+ 旧别名（`--bg`/`--text`/`--accent` 等映射到浅色）
- Produces: `.card` `.btn-primary` `.btn-ghost` `.input-field` 表格基础样式

- [ ] **Step 1: 重写 `frontend/src/style.css`**

完整替换为（可微调，但 token 值必须与 spec 一致）：

```css
:root {
  color-scheme: light;

  --brand: #e66432;
  --brand-light: #fef3ee;
  --brand-soft: #f9d4c4;
  --brand-dark: #c45228;
  --brand-foreground: #ffffff;

  --surface: #ffffff;
  --surface-muted: #f5f5f5;
  --ink: #404040;
  --ink-muted: #737373;
  --ink-faint: #a3a3a3;
  --line: #e5e5e5;
  --line-soft: #f0f0f0;

  --shadow-card: 0 1px 3px rgba(0, 0, 0, 0.04), 0 4px 12px rgba(230, 100, 50, 0.06);
  --shadow-panel: 0 4px 24px rgba(0, 0, 0, 0.06);

  --danger: #e11d48;
  --ok: #16a34a;

  --font:
    "PingFang SC", "Microsoft YaHei", "Segoe UI", system-ui, -apple-system, sans-serif;
  --mono: "SF Mono", "Menlo", "Consolas", ui-monospace, monospace;

  /* 旧变量别名：让现有 view 立刻变浅色 */
  --bg: var(--surface-muted);
  --bg-elevated: var(--surface);
  --bg-panel: var(--surface);
  --border: var(--line);
  --text: var(--ink);
  --muted: var(--ink-muted);
  --accent: var(--brand);
  --accent-hover: var(--brand-dark);
}

* {
  box-sizing: border-box;
}

html,
body,
#app {
  margin: 0;
  min-height: 100%;
  height: 100%;
  background: var(--surface-muted);
  color: var(--ink);
  font-family: var(--font);
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

a {
  color: inherit;
  text-decoration: none;
}

button,
input,
select,
textarea {
  font: inherit;
}

button {
  cursor: pointer;
}

table {
  border-collapse: collapse;
  width: 100%;
}

table th {
  color: var(--ink-muted);
  font-weight: 500;
  text-align: left;
  background: var(--surface-muted);
}

table th,
table td {
  border-bottom: 1px solid var(--line);
  padding: 0.5rem 0.75rem;
}

table tbody tr:hover td {
  background: var(--brand-light);
}

.card {
  border-radius: 0.75rem;
  border: 1px solid var(--line);
  background: var(--surface);
  box-shadow: var(--shadow-card);
}

.btn-primary {
  border-radius: 0.5rem;
  border: none;
  background: var(--brand);
  color: var(--brand-foreground);
  padding: 0.5rem 1rem;
  font-size: 0.875rem;
  font-weight: 500;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);
  transition: background 0.15s ease;
}

.btn-primary:hover:not(:disabled) {
  background: var(--brand-dark);
}

.btn-primary:disabled {
  cursor: not-allowed;
  opacity: 0.5;
}

.btn-ghost {
  border-radius: 0.5rem;
  border: 1px solid var(--line);
  background: transparent;
  color: var(--ink-muted);
  padding: 0.375rem 0.75rem;
  font-size: 0.875rem;
  transition: background 0.15s ease, color 0.15s ease, border-color 0.15s ease;
}

.btn-ghost:hover:not(:disabled) {
  background: var(--brand-light);
  color: var(--brand);
  border-color: var(--brand-soft);
}

.input-field {
  width: 100%;
  border-radius: 0.5rem;
  border: 1px solid var(--line);
  background: var(--surface);
  color: var(--ink);
  padding: 0.5rem 0.75rem;
  font-size: 0.875rem;
  outline: none;
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
}

.input-field::placeholder {
  color: var(--ink-faint);
}

.input-field:focus {
  border-color: var(--brand);
  box-shadow: 0 0 0 3px rgba(230, 100, 50, 0.15);
}

.nav-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
  width: 100%;
  border: none;
  border-radius: 0.5rem;
  background: transparent;
  color: var(--ink-muted);
  padding: 0.625rem 0.75rem;
  text-align: left;
  font-size: 0.875rem;
  transition: background 0.15s ease, color 0.15s ease;
}

.nav-item:hover {
  background: rgba(254, 243, 238, 0.7);
  color: var(--ink);
}

.nav-item-active {
  background: var(--brand-light);
  color: var(--brand);
  font-weight: 500;
}

.nav-item-active:hover {
  background: var(--brand-light);
  color: var(--brand);
}
```

- [ ] **Step 2: 构建校验**

Run: `cd frontend && npm run build`  
Expected: 成功（无 TS/Vue 编译错误）

- [ ] **Step 3: Commit**

```bash
git add frontend/src/style.css
git commit -m "$(cat <<'EOF'
style(ui): 引入 MilesAI 浅色橙品牌 token 与通用组件类

为壳层与业务页浅色适配提供统一变量与别名。
EOF
)"
```

---

### Task 2: AppShell 浅色侧栏与顶栏

**Files:**
- Modify: `frontend/src/components/AppShell.vue`
- Test: 浏览器打开任意已登录页，或 `npm run build`

**Interfaces:**
- Consumes: `--surface` `--brand-light` `--brand` `--line` `--ink*`；可选 `.nav-item` / `.btn-ghost`
- Produces: 白侧栏、橙激活态、白顶栏、浅灰内容底

- [ ] **Step 1: 更新 `AppShell.vue` template 类名（可选但推荐）**

将侧栏链接改为使用全局导航类；退出按钮用 `.btn-ghost`：

```vue
<template>
  <div class="shell">
    <aside class="side">
      <div class="logo">
        <span class="logo-mark" aria-hidden="true" />
        zak2
      </div>
      <nav>
        <RouterLink
          v-for="item in navItems"
          :key="item.key"
          class="nav-item"
          :class="{ 'nav-item-active': active === item.key, muted: !item.enabled }"
          :to="item.enabled && 'to' in item ? item.to : '#'"
          @click="(e) => { if (!item.enabled) e.preventDefault() }"
        >
          {{ item.label }}
          <span v-if="!item.enabled" class="soon">稍后</span>
        </RouterLink>
      </nav>
    </aside>
    <div class="main">
      <header class="top">
        <div>
          <h1>{{ title }}</h1>
          <p v-if="subtitle" class="meta">{{ subtitle }}</p>
        </div>
        <div class="user">
          <span>{{ auth.user?.display_name || auth.user?.username }}</span>
          <button class="btn-ghost" type="button" @click="logout">退出</button>
        </div>
      </header>
      <div class="body">
        <slot />
      </div>
    </div>
  </div>
</template>
```

- [ ] **Step 2: 替换 scoped 样式**

```css
.shell {
  display: grid;
  grid-template-columns: 220px 1fr;
  height: 100%;
  background: var(--surface-muted);
}
.side {
  border-right: 1px solid var(--line);
  background: var(--surface);
  padding: 16px 12px;
  display: flex;
  flex-direction: column;
  gap: 18px;
}
.logo {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 700;
  letter-spacing: 0.04em;
  padding: 4px 8px;
  color: var(--ink);
}
.logo-mark {
  width: 8px;
  height: 8px;
  border-radius: 2px;
  background: var(--brand);
  flex-shrink: 0;
}
.nav-item.muted {
  color: var(--ink-faint);
  pointer-events: none;
}
.soon {
  font-size: 0.7rem;
  opacity: 0.7;
}
.main {
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
}
.top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  height: 56px;
  padding: 0 20px;
  border-bottom: 1px solid var(--line);
  background: var(--surface);
}
.top h1 {
  margin: 0;
  font-size: 1.125rem;
  font-weight: 600;
  color: var(--ink);
}
.meta {
  margin: 2px 0 0;
  color: var(--ink-muted);
  font-size: 0.8125rem;
}
.user {
  display: flex;
  gap: 12px;
  align-items: center;
  color: var(--ink-muted);
  font-size: 0.875rem;
}
.body {
  flex: 1;
  min-height: 0;
  overflow: auto;
  padding: 16px 20px;
}
@media (max-width: 900px) {
  .shell {
    grid-template-columns: 1fr;
  }
  .side {
    display: none;
  }
}
```

删除旧的 `.nav` / `.ghost` / `#0c1118` 等深色规则。

- [ ] **Step 3: 构建校验**

Run: `cd frontend && npm run build`  
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/AppShell.vue
git commit -m "$(cat <<'EOF'
style(ui): AppShell 改为浅色侧栏与橙激活态

对齐 MilesAI 导航视觉，保留原有左侧栏信息架构。
EOF
)"
```

---

### Task 3: 登录页浅色卡片

**Files:**
- Modify: `frontend/src/views/LoginView.vue`
- Test: `/login` 目视 + build

**Interfaces:**
- Consumes: `.card` `.btn-primary` `.input-field`；`--brand-*` `--surface*` `--ink*`

- [ ] **Step 1: 更新 template**

```vue
<template>
  <div class="page">
    <form class="card form" @submit.prevent="onSubmit">
      <div class="brand">
        <span class="logo-mark" aria-hidden="true" />
        zak2
      </div>
      <p class="sub">使用与桌面端相同的账号登录</p>
      <label>
        用户名
        <input class="input-field" v-model="username" autocomplete="username" required />
      </label>
      <label>
        密码
        <input
          class="input-field"
          v-model="password"
          type="password"
          autocomplete="current-password"
          required
        />
      </label>
      <p v-if="error" class="err">{{ error }}</p>
      <button class="btn-primary" type="submit" :disabled="loading">
        {{ loading ? '登录中…' : '登录' }}
      </button>
    </form>
  </div>
</template>
```

- [ ] **Step 2: 替换 scoped 样式**

```css
.page {
  min-height: 100%;
  display: grid;
  place-items: center;
  background: var(--surface-muted);
  padding: 24px;
}
.form {
  width: min(380px, 100%);
  padding: 28px 24px;
  display: grid;
  gap: 14px;
}
.brand {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 1.75rem;
  font-weight: 700;
  letter-spacing: 0.04em;
  color: var(--ink);
}
.logo-mark {
  width: 10px;
  height: 10px;
  border-radius: 2px;
  background: var(--brand);
}
.sub {
  margin: -6px 0 4px;
  color: var(--ink-muted);
  font-size: 0.9rem;
}
label {
  display: grid;
  gap: 6px;
  color: var(--ink);
  font-size: 0.875rem;
  font-weight: 500;
}
.err {
  margin: 0;
  border-radius: 0.5rem;
  background: var(--brand-light);
  color: var(--brand-dark);
  padding: 0.5rem 0.75rem;
  font-size: 0.875rem;
}
.btn-primary {
  width: 100%;
  margin-top: 4px;
}
```

删除深蓝径向渐变与旧深色 input/button 规则。

- [ ] **Step 3: 构建校验**

Run: `cd frontend && npm run build`  
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add frontend/src/views/LoginView.vue
git commit -m "$(cat <<'EOF'
style(ui): 登录页改为浅色橙品牌卡片

去掉深色渐变底，对齐 MilesAI 登录表单节奏。
EOF
)"
```

---

### Task 4: 业务页硬编码深色清理

**Files:**
- Modify（按需）:
  - `frontend/src/views/WatchlistView.vue`
  - `frontend/src/views/MarketView.vue`
  - `frontend/src/views/SectorView.vue`
  - `frontend/src/views/RadarView.vue`
  - `frontend/src/views/ScreenerHubView.vue`
  - `frontend/src/views/BacktestView.vue`
  - `frontend/src/views/OpsView.vue`
  - `frontend/src/views/AiView.vue`
  - `frontend/src/views/FeedView.vue`
  - `frontend/src/views/NotesView.vue`
  - `frontend/src/views/PlaybookView.vue`
- Test: build + 抽查主要页面对比度

**Interfaces:**
- Consumes: Task 1 别名（`--bg`/`--border`/`--accent` 已浅色）
- Produces: 无大块 `#0x`/`#1x` 深蓝面板；表格表头 hover 可读

- [ ] **Step 1: 全局替换硬编码深色面板色**

在各 view 的 `<style scoped>` 中，将下列值替换为 token（保持语义）：

| 旧值（示例） | 新值 |
|--------------|------|
| `#0d1219` `#0e141d` `#0c1118` `#0b1020` | `var(--surface-muted)` 或 `var(--surface)` |
| `#121924` `#1c2838` | `var(--surface-muted)`（表头/条纹） |
| `#2a1c1c` `#3a2424` | 保留或改为更浅的危险浅底 `var(--brand-light)` / `#fee2e2`（仅风险高亮行） |
| `#24553a` `#2f6b48` `#d8ffe8` | 改为浅绿语义：`#ecfdf5` 底 + `#166534` 字（Ops 成功态） |
| `#2f4d73` `#3d5a80` `#2f5540` | `var(--brand-soft)` 或 `var(--line)`（边框强调） |
| sparkline `stroke="#3d8bfd"` | `stroke="var(--brand)"` 或 `#e66432` |
| Radar 主按钮 `color: #0b1020` | `color: var(--brand-foreground)` |

原则：

1. 已用 `var(--bg*)` / `var(--accent)` 的规则一般无需改（别名已浅色）。
2. 只改硬编码 hex 与明显对比失败处。
3. **不要**把涨跌 `--danger`/`--ok` 改成 brand。

可用 ripgrep 核对残留：

```bash
rg -n '#[0-1][0-9a-fA-F]{5}|#2[0-9a-fA-F]{5}' frontend/src/views frontend/src/components --glob '*.vue'
```

Expected: 无深蓝终端色；允许涨跌红绿、品牌橙、语义成功绿。

- [ ] **Step 2: 构建校验**

Run: `cd frontend && npm run build`  
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add frontend/src/views
git commit -m "$(cat <<'EOF'
style(ui): 清理业务页硬编码深色面板色

依赖全局浅色别名，定点替换残留 hex 以恢复对比度。
EOF
)"
```

---

### Task 5: CandleChart 浅色可读性

**Files:**
- Modify: `frontend/src/components/CandleChart.vue`
- Test: 自选页有 K 线时目视；build

**Interfaces:**
- Produces: 浅底图表容器；涨跌色仍为红/绿（可保持 `#d4544a` / `#3fae6c`）

- [ ] **Step 1: 调整图表容器与轴线样式**

在 `CandleChart.vue` 的 scoped CSS 中，确保：

```css
.wrap {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: 0.75rem;
}
/* 轴线/标签已用 var(--muted) 即可；若有硬编码深色 stroke 改为 var(--line) */
```

若 SVG 背景透明且父级已是浅色，至少保证标签 `fill: var(--ink-muted)`。  
**不要**改 `color: up ? '#d4544a' : '#3fae6c'`。

- [ ] **Step 2: 构建校验**

Run: `cd frontend && npm run build`  
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/CandleChart.vue
git commit -m "$(cat <<'EOF'
style(ui): K 线图适配浅色背景

保留涨跌语义色，仅调整容器与轴标签对比度。
EOF
)"
```

---

### Task 6: 验收扫尾

**Files:**
- 按需微调上述文件
- 可选：更新 `docs/smoke-checklist.md` 增加一条 UI 浅色验收（非必须）

- [ ] **Step 1: 对照 spec 验收清单**

手动或开发服检查：

1. 整体浅色；主强调为橙  
2. 侧栏激活浅橙底 + 橙字；顶栏白；退出可用  
3. 登录白卡 + 橙按钮 + 错误浅橙提示  
4. 自选 / 市场 / 选股 / Ops 无白字压白底、无大块深蓝孤岛  
5. 涨跌色可辨；K 线可读  
6. `cd frontend && npm run build` 通过  

- [ ] **Step 2: 若有散落修复，一并 commit**

```bash
git add frontend/src
git commit -m "$(cat <<'EOF'
style(ui): 浅色主题验收扫尾

补齐对比度与残留深色块。
EOF
)"
```

（若无需改动则跳过本 commit。）

---

## Spec coverage（自检）

| Spec 要求 | Task |
|-----------|------|
| Token / 别名 / color-scheme light | 1 |
| 全局 `.card` `.btn-*` `.input-field` 表格 | 1 |
| AppShell 侧栏+顶栏浅色橙激活 | 2 |
| Login 浅色卡 | 3 |
| 业务页硬编码适配 | 4 |
| CandleChart | 5 |
| 验收标准 / build | 1–6 |
| 非目标（Tailwind、顶栏主导航、Hero、暗色切换） | 全计划未包含 |

## Placeholder scan

无 TBD / “similar to Task N” / 空测试步骤。UI 以 build + 目视验收替代单元测试（本仓前端无组件测试基建）。

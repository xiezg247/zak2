# zak2 UI 对齐 MilesAI 浅色橙品牌设计

日期：2026-08-11  
状态：已批准（方案 1：CSS 变量 + 组件级样式升级）  
范围：仅 `frontend/`；参考 `/Users/xiezhigang/Projects/miles/MilesAI/ui` 视觉语言；不迁移框架、不引入 Tailwind

## 背景

zak2 前端为 Vue 3 + Vite，当前为深色交易终端风格（`--bg: #0f1419`、蓝强调色、左侧栏）。  
MilesAI workbench 为浅色工作台（橙品牌 `#E66432`、白卡片、顶栏主导航、Tailwind）。

用户要求：**参考 MilesAI 重新设计 zak2 样式与布局**，并确认：

| 项 | 选择 |
|----|------|
| 主题 | A：浅色底 + 橙色品牌 |
| 布局 | B：保留左侧栏，换成 MilesAI 视觉与卡片节奏 |
| 范围 | A：全局壳层优先（主题、侧栏/顶栏、登录、通用组件）；业务页轻量适配 |
| 实现 | 1：CSS 变量 + 组件级样式，不引入 Tailwind |

## 目标

1. 全局视觉从深色终端切换为 MilesAI 同系浅色橙品牌。  
2. `AppShell`（侧栏 + 顶栏 + 内容区）与 `LoginView` 观感对齐 MilesAI。  
3. 提供可复用的全局类（卡片 / 按钮 / 输入框 / 导航 / 表格），业务页用 token 与类做浅色适配。  
4. 保持现有路由、导航顺序、交互与业务逻辑不变。

## 非目标

- 引入 Tailwind / UnoCSS，或把 Vue 栈迁到 Next.js  
- 改成顶栏主导航或 business/system 双壳  
- 逐页重排 DOM / 新信息架构  
- 暗色模式切换、移动端抽屉导航  
- 登录页左右分栏 Hero / 搬迁 MilesAI 公司 Logo  
- 改后端 API 或产品功能

## 决策摘要

| 项 | 选择 |
|----|------|
| 主题 | 浅色 + `#E66432` 品牌橙 |
| 壳层 | 保留 `侧栏 + 主区`，白底侧栏/顶栏，灰底内容区 |
| 实现 | `style.css` token + 全局组件类；`AppShell` / `LoginView` 重写样式 |
| 业务页 | 硬编码深色色值改为 token/类；结构不大改 |
| 涨跌色 | 保留红涨绿跌语义色，不与品牌橙混用 |

---

## 1. 视觉 Token

在 `frontend/src/style.css` 的 `:root` 替换为浅色体系（对齐 MilesAI `globals.css` / `tailwind.config.ts`）：

| Token | 值 | 用途 |
|-------|-----|------|
| `--brand` | `#E66432` | 主按钮、激活态、强调 |
| `--brand-light` | `#FEF3EE` | 导航激活底、错误浅底 |
| `--brand-soft` | `#F9D4C4` | 轻强调 |
| `--brand-dark` | `#C45228` | 主按钮 hover |
| `--brand-foreground` | `#FFFFFF` | 主按钮字色 |
| `--surface` | `#FFFFFF` | 卡片、侧栏、顶栏 |
| `--surface-muted` | `#F5F5F5` | 页面底 |
| `--ink` | `#404040` | 正文 |
| `--ink-muted` | `#737373` | 次要文字 |
| `--ink-faint` | `#A3A3A3` | 占位 / 禁用 |
| `--line` | `#E5E5E5` | 边框 |
| `--line-soft` | `#F0F0F0` | 轻分割 |
| `--shadow-card` | `0 1px 3px rgba(0,0,0,0.04), 0 4px 12px rgba(230,100,50,0.06)` | 卡片 |
| `--shadow-panel` | `0 4px 24px rgba(0,0,0,0.06)` | 浮层 |

字体：中文可读栈（`PingFang SC` / `Microsoft YaHei` + system-ui）；不再以 IBM Plex 作为主视觉。  
`color-scheme: light`。

兼容：可保留旧变量别名（如 `--bg` → `--surface-muted`、`--text` → `--ink`、`--accent` → `--brand`）以降低业务页一次性改动量，但新代码以新 token 为准。

业务语义色（涨跌红绿、图表序列色）继续独立定义，不并入 brand。

---

## 2. 壳层布局（`AppShell.vue`）

结构保持：

```text
[ aside 侧栏 ~220px ] [ main: header 顶栏 + body 内容 ]
```

### 侧栏

- 背景 `--surface`，右边框 `--line`
- Logo：`zak2`（品牌橙点缀，如色条或字色强调）
- 导航项圆角；激活：`--brand-light` 底 + `--brand` 字色；idle：`--ink-muted`；hover：浅橙底
- 导航顺序不变：守则 / 自选 / 市场 / 板块资金 / 雷达 / 选股 / 回测 / 信息流 / 笔记 / AI / 运维
- `≤900px`：侧栏仍隐藏（与现状一致；本期不做抽屉）

### 顶栏

- 高约 56px，白底，底部分割线
- 左：`title` + 可选 `subtitle`
- 右：用户名 + 退出（幽灵按钮：灰边；hover 浅橙底 / 橙字）

### 内容区

- 底色 `--surface-muted`，内边距约 `16–24px`，可滚动
- 业务页结构不大改；卡片自然落在白底上

---

## 3. 登录页（`LoginView.vue`）

- 全屏 `--surface-muted`，居中白卡片（圆角 + `--shadow-card`）
- 品牌标题 + 副文案「使用与桌面端相同的账号登录」
- 输入框：白底、灰边；focus：橙边 + 浅橙 ring
- 主按钮：满宽橙底白字；hover `--brand-dark`
- 错误：`--brand-light` 底 + `--brand-dark` 字
- 不做左右 Hero 分栏

---

## 4. 全局通用类（`style.css`）

| 类名 | 行为（对齐 MilesAI 意图） |
|------|---------------------------|
| `.card` | 白底、圆角、边框、`--shadow-card` |
| `.btn-primary` | 橙底白字主按钮 |
| `.btn-ghost` | 透明/浅灰次要按钮；hover 浅橙 |
| `.input-field` | 统一输入框 focus 环 |
| `.nav-item` / `.nav-item-active` | 侧栏导航态（亦可在 AppShell scoped 内等价实现） |
| 表格基础 | 表头 muted、行 `--line` 分割、hover 浅底 |

`AppShell` / `LoginView` 优先使用上述类或等价 token；各 `views/*.vue` 中硬编码深色背景/边框/文字改为 token 或类，**不重排版面**。

---

## 5. 文件与改动清单

| 文件 | 改动 |
|------|------|
| `frontend/src/style.css` | 新 token、全局组件类、表格/链接基础、旧变量别名 |
| `frontend/src/components/AppShell.vue` | 侧栏/顶栏浅色样式；导航激活态对齐 brand |
| `frontend/src/views/LoginView.vue` | 浅色登录卡 |
| `frontend/src/views/*.vue` | 仅替换与深色主题冲突的颜色/边框（必要时） |
| `frontend/src/components/CandleChart.vue` | 若图表背景绑死深色，改为可读浅色网格/轴色（保持涨跌语义） |

不改：`package.json` 依赖、路由、API、stores（除非仅样式引用）。

---

## 6. 验收标准

1. 登录后整体为浅色工作台；主强调色为橙色，无大块深蓝底。  
2. 侧栏激活项为浅橙底 + 橙字；顶栏白底、退出按钮可用。  
3. 登录页白卡 + 橙主按钮 + 错误浅橙提示。  
4. 主要业务页（自选 / 市场 / 选股 / Ops 等）文字对比可读，无「白字压白底」或「深色孤岛」大块残留。  
5. 涨跌色仍可辨识；图表在浅色背景下可读。  
6. `npm run build` 通过。

---

## 7. 风险与缓解

| 风险 | 缓解 |
|------|------|
| 各 view 内大量 scoped 深色硬编码 | 先全局 token + 别名；再按对比失败处定点替换 |
| 图表默认按深色配置 | 单独调 CandleChart 轴/网格/背景 |
| 橙品牌与涨跌红混淆 | brand 仅用于 chrome；涨跌用独立语义色 |

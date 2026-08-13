# 笔记安全操作与研报 Tab 薄打磨设计

日期：2026-08-13  
状态：已批准（方案 A：NotesView + AiView 预填；不做移出侧栏）  
范围：zak2 `NotesView` / `AiView`；不改 notes REST 契约

## 背景

#31 已做侧栏过滤空态。仍缺：删流水无 confirm；研报空态仅文案、无过滤、无去 AI 入口；`/ai` 投研框不读 `?symbol=`。

## 目标

1. 删流水前 `window.confirm`。  
2. 研报 Tab：标题/摘要轻过滤；无研报链 `/ai?symbol=`；无匹配文案。  
3. `AiView` 用 query `symbol` 预填 `teamSymbol`（不自动开跑）。  
4. 更新 smoke 与路线图 #32。

## 非目标

- 按标的删除备忘+流水 / 移出侧栏 API  
- 改 notes REST 语义  
- 研报排序、批量删、自动启动投研团队  
- 改 Feed / 其它页

## 决策摘要

| 项 | 选择 |
|----|------|
| 方案 | A |
| confirm 文案 | `确定删除这条流水？` |
| 研报过滤 | `title` + `summary` |
| AI 链 | `RouterLink` → `/ai?symbol=<encodeURIComponent(selected)>` |
| AiView | 仅预填，不 `runTeam` |

---

## 1. NotesView

### 1.1 删流水

```ts
async function removeEntry(id: number) {
  if (!window.confirm('确定删除这条流水？')) return
  // 现有 delete + reload
}
```

### 1.2 研报过滤与空态

- `reportFilter` ref；`displayedReports` computed（有 `reports.length` 时显示过滤框）。  
- `!reports.length`：muted 文案 + 链到 AI（文案含「去 AI」或「跑投研团队」）。  
- `reports.length && !displayedReports.length`：「无匹配研报」。  
- `v-for` 用 `displayedReports`；点开详情逻辑不变。

### 1.3 数据流

```
reports (API) → text filter → displayedReports → 列表
```

---

## 2. AiView

- `useRoute()`。  
- 挂载时：`const s = String(route.query.symbol || '').trim()`；非空则 `teamSymbol.value = s`。  
- 不自动调用 `runTeam`。

---

## 3. 模块

| 路径 | 职责 |
|------|------|
| `frontend/src/views/NotesView.vue` | confirm、研报过滤/空态/链 |
| `frontend/src/views/AiView.vue` | query 预填 teamSymbol |
| `docs/smoke-checklist.md` | 验收条 |
| `docs/product-roadmap.md` | #32 |

---

## 4. 验收

1. 删流水弹出 confirm；取消不删。  
2. 有研报可过滤；无匹配见「无匹配研报」。  
3. 无研报可见去 AI 链接，且带当前 `selected`。  
4. `/ai?symbol=600519.SSE` 打开后投研输入框为该代码。  
5. smoke + roadmap 已更新。

## 风险

用户取消 confirm 后焦点行为因浏览器而异，可接受。

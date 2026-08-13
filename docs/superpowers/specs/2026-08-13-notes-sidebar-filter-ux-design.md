# 笔记侧栏过滤与空态 UX 设计

日期：2026-08-13  
状态：已批准（方案 A：纯前端；代码+备忘预览过滤；保持 selected）  
范围：仅 zak2 `NotesView`；不改 notes REST / 研报 / 流水删除

## 背景

`/notes` 已有标的列表、备忘/流水、研报 Tab 与 query 直达。侧栏无过滤；空态未区分「暂无标的 / 无匹配 / 加载中」，与 Feed #23 体验不一致。

## 目标

1. 左侧按代码 / 备忘预览过滤。  
2. 空态三分（加加载）：加载中 / 暂无笔记标的 / 无匹配标的。  
3. 更新 smoke 与路线图。

## 非目标

- 改 `/api/v1` notes 契约或服务端搜索  
- 研报 Tab 打磨、删流水 confirm、移出列表  
- 过滤时自动清空 `selected`（本刀 **保持** selected，详情仍可读）

## 决策摘要

| 项 | 选择 |
|----|------|
| 方案 | A：纯前端 `displayedSymbols` |
| 匹配 | `vt_symbol` + `memo_preview`（trim，大小写不敏感） |
| 过滤框可见 | `symbols.length > 0` |
| 选中被滤掉 | 保持 `selected`；列表中该行不可见但不强制清选中 |

---

## 1. UI 行为

### 1.1 过滤

- 「打开」输入行下方：`<input>` placeholder「过滤代码/备忘」  
- `query` → `displayedSymbols`  
- `v-for="s in displayedSymbols"`

### 1.2 数据流

```
symbols (API) → text filter(query) → displayedSymbols → 列表
```

打开 / 保存 / 流水 / 研报 / `?symbol=` **不变**。

### 1.3 空态

| 条件 | 左侧 | 右侧 |
|------|------|------|
| `loading` | 「加载中…」 | 可选同文案 |
| `!loading && !symbols.length` | 打开表单 +「输入代码打开笔记」 | 「暂无笔记标的」 |
| `symbols.length && !displayedSymbols.length` | 过滤框 + 「无匹配标的」 | 有 `selected` 则仍显示详情；否则「选择或打开一只股票」 |
| 有匹配 | 列表 | 现有右栏 |

错误态保持现有 `error` 行。

### 1.4 loading

`onMounted` / 首次 `loadSymbols`（及必要时 `loadDetail`）期间 `loading=true`；结束后 false。不必为每次切换标的全页 loading。

---

## 2. 模块

| 路径 | 职责 |
|------|------|
| `frontend/src/views/NotesView.vue` | query、displayedSymbols、loading、空态、样式 |
| `docs/smoke-checklist.md` | `/notes` 过滤与空态验收 |
| `docs/product-roadmap.md` | 近期待办完成项（建议 #31） |

---

## 3. 验收

1. 有标的时可过滤代码/备忘；无匹配见「无匹配标的」。  
2. 无标的见「暂无笔记标的」与打开引导。  
3. 加载中可见「加载中…」。  
4. 过滤隐藏当前选中时，右侧详情仍可读（不强制清 selected）。  
5. smoke + roadmap 已更新。

## 风险

标的很多时纯前端过滤足够；若未来上千条再考虑服务端。

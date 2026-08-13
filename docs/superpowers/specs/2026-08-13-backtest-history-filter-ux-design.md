# 回测历史过滤与空态 UX 设计

日期：2026-08-13  
状态：已批准（方案 A：纯前端；标的+策略过滤；轻量选中高亮）  
范围：仅 zak2 `BacktestView`；不改 backtest API / 引擎

## 背景

`/backtest` 已有单票/批量双均线、历史、权益折线与批次对比。历史无过滤；空态未区分加载中 / 无历史 / 无匹配；当前打开的 run 无高亮。与笔记侧栏 #31 体验不一致。

## 目标

1. 历史按标的 / 策略过滤；批次按策略共用同一 query（薄）。  
2. 空态：加载中 / 暂无回测历史 / 无匹配历史。  
3. 历史项选中高亮。  
4. 更新 smoke 与路线图 #33。

## 非目标

- 改 `/api/v1/backtest/*` 或引擎  
- 日 K 不足 Ops 链、画像 chip 填参、图表增强  
- 删除历史、对比多选

## 决策摘要

| 项 | 选择 |
|----|------|
| 方案 | A + 轻量 `.on` 高亮 |
| 历史匹配 | `vt_symbol` + `strategy` |
| 批次匹配 | 同一 `listFilter` → `strategy` |
| 选中被滤掉 | 保持 `selected`，详情仍可读 |
| 列表上限 | 仍 `displayedRuns.slice(0, 30)` |

---

## 1. UI 行为

### 1.1 过滤

- 「历史」下：`input` placeholder「过滤标的/策略」（`runs.length > 0`）。  
- `listFilter` → `displayedRuns` / `displayedBatches`。  
- 批次区标题仍 `v-if="batches.length"`；列表用 `displayedBatches`；无匹配时可在批次区显示「无匹配批次」或仅空列表——**推荐**：有 `batches.length && listFilter && !displayedBatches.length` 时一行「无匹配批次」。

### 1.2 空态

| 条件 | 左侧历史区 | 右侧 |
|------|------------|------|
| `loading` | 「加载中…」 | 「加载中…」 |
| `!loading && !runs.length` | 「暂无回测历史」 | 「运行回测或从左侧打开历史记录」 |
| `runs.length && !displayedRuns.length` | 过滤框 + 「无匹配历史」 | 有 `selected` 则详情；否则同上 empty |
| 有匹配 | 列表 | 现有 |

`refresh` / `onMounted` 用 `loading` 包裹。

### 1.3 选中高亮

```vue
:class="{ on: selected?.id === r.id }"
```

样式对齐笔记侧栏选中边框。

---

## 2. 模块

| 路径 | 职责 |
|------|------|
| `frontend/src/views/BacktestView.vue` | filter、空态、loading、高亮 |
| `docs/smoke-checklist.md` | `/backtest` 验收条 |
| `docs/product-roadmap.md` | #33 |

---

## 3. 验收

1. 有历史时可按标的/策略过滤；无匹配见「无匹配历史」。  
2. 无历史见「暂无回测历史」。  
3. 加载中可见提示。  
4. 打开某条历史该项高亮；过滤隐藏后详情仍可读。  
5. smoke + roadmap 已更新。

## 风险

历史默认最多展示 30 条过滤结果切片，与现行为一致。

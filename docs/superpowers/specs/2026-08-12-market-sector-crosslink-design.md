# 市场 ↔ 板块页眉互链 设计

日期：2026-08-12  
状态：已批准（方案 A：页内 toolbar RouterLink；无 query）  
范围：仅 zak2 `MarketView` / `SectorView` 工具条互链；不改 AppShell / API

## 背景

顶栏已有「市场」「板块资金」导航，页内无快捷互跳；看完排行想切资金流（或反之）需回顶栏。

## 目标

1. 市场页工具条提供「板块资金 →」链到 `/sectors`。  
2. 板块页工具条提供「← 市场」链到 `/market`。  
3. 无 query、不改现有业务逻辑。

## 非目标

- query 预选 kind/日期/field  
- 成分股下钻、板块行点进市场排行  
- 改 AppShell 导航结构或副标题 slot  
- 改 ranks / sectorFlow API

## 决策摘要

| 项 | 选择 |
|----|------|
| 方案 | A：toolbar 内 `RouterLink` |
| 路由 | `/market` ↔ `/sectors`，无 query |
| 文案 | 「板块资金 →」/「← 市场」 |

---

## 1. UI 行为

### 1.1 市场页

在现有 `.toolbar` 的 `.actions` 中（刷新旁）增加：

```html
<RouterLink to="/sectors" class="cross-link">板块资金 →</RouterLink>
```

### 1.2 板块页

在现有 `.toolbar` 末尾（或右侧 actions 容器）增加：

```html
<RouterLink to="/market" class="cross-link">← 市场</RouterLink>
```

### 1.3 样式

两页共用语义类 `.cross-link`（可各自 scoped 复制一小段）：`color: var(--brand)` 或 `var(--accent)`，与现有 `draft-link` 接近；不抢主按钮视觉。

---

## 2. 模块

| 路径 | 职责 |
|------|------|
| `frontend/src/views/MarketView.vue` | 链到板块 |
| `frontend/src/views/SectorView.vue` | 链到市场 |
| `docs/smoke-checklist.md` | 互跳检查项 |
| `docs/product-roadmap.md` | 近期待办条目 |

---

## 3. 验收

1. `/market` 点「板块资金 →」进入板块页。  
2. `/sectors` 点「← 市场」进入市场页。  
3. 排行过滤、情绪周期、板块表过滤排序不受影响。  
4. `./scripts/check.sh` 绿。

## 4. 风险

- 与顶栏导航功能重叠——页内链缩短路径即可，可接受。  
- 两页 scoped 样式重复 —— 本刀不做共享 CSS 抽取（YAGNI）。

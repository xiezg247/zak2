# 板块空态 Ops 链与雷达共振过滤 UX 设计

日期：2026-08-13  
状态：已批准（方案 A：纯前端；板块去 Ops；共振按代码/名称过滤）  
范围：zak2 `SectorView` + `RadarView`；不改 sector / radar API

## 背景

`/sectors` 无数据时空态仅文案提 `sync_sector_flow_daily`，无可点 Ops（市场 #36 / 情绪已有）。`/radar` 共振侧栏直接列出全部条目，无代码/名称过滤与「无匹配」空态；卡片区过滤已在 #18。

## 目标

1. 板块真无数据空态旁挂「去 Ops」。  
2. 共振侧栏按 `vt_symbol` / `name` 过滤；区分真无共振 vs 无匹配。  
3. 更新 smoke 与路线图 #38。

## 非目标

- 改 sector flow / radar resonance API  
- 板块成分下钻、雷达卡片网格再改、展望区、权重逻辑  
- 「无匹配板块」挂 Ops

## 决策摘要

| 项 | 选择 |
|----|------|
| 方案 | A：纯前端 |
| 板块链文案 | 「去 Ops」 |
| 共振匹配 | `vt_symbol` + `name` |
| 共振过滤框 | `resonance.length > 0` |
| 路线图 | 一项 #38 覆盖两切面 |

---

## 1. 板块（SectorView）

现有：

```text
暂无板块资金。可先到 Ops 执行 sync_sector_flow_daily。
```

同段增加：

```vue
<RouterLink to="/ops" class="draft-link">去 Ops</RouterLink>
```

复用或补 `.draft-link` 样式（对齐 MarketView）。过滤无匹配「无匹配板块」不变。

---

## 2. 雷达共振（RadarView）

### 2.1 过滤

- `resonanceFilter` ref  
- `displayedResonance` computed：trim + lower，`vt_symbol` / `name` includes  
- 侧栏列表上方（权重区与列表之间，或列表顶）：`v-if="resonance.length"` 的 input，placeholder「过滤代码/名称」  
- `v-for="e in displayedResonance"`

### 2.2 空态

| 条件 | 侧栏列表区 |
|------|------------|
| `!resonance.length` | 现有「暂无共振标的（需至少 2 张…）」 |
| `resonance.length && !displayedResonance.length` | 过滤框 +「无匹配共振」 |
| 有匹配 | 过滤框 + 行 |

权重、Hub 按钮、加自选、`sideMsg` 不变。

---

## 3. 模块

| 路径 | 职责 |
|------|------|
| `frontend/src/views/SectorView.vue` | Ops 链 + 样式 |
| `frontend/src/views/RadarView.vue` | `resonanceFilter` / `displayedResonance` / 空态 |
| `docs/smoke-checklist.md` | `/sectors`、`/radar` 验收 |
| `docs/product-roadmap.md` | #38 |

---

## 4. 验收

1. `/sectors` 无数据见原空态文案 +「去 Ops」。  
2. `/radar` 有共振时可按代码/名称过滤；无匹配见「无匹配共振」；真无共振文案不变。  
3. 板块过滤排序、雷达卡片/权重/展望不变。  
4. smoke + roadmap 已更新。

## 风险

无；纯前端展示层。

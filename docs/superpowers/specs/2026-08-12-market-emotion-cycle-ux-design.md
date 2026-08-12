# 市场情绪周期展示 UX 设计

日期：2026-08-12  
状态：已批准（方案 A：纯前端展示层；不改判定/阈值 API）  
范围：仅 zak2 `MarketView` 情绪周期卡片与阈值入口；不改排行表、板块页

## 背景

情绪周期卡片已展示阶段、仓位、可否新开、警告与 inputs，下方可折叠判定阈值。痛点：信息平铺难扫；无周期时仅「暂无数据」且无 Ops 预热指引；阈值入口仅在卡片下方，卡片上无快捷展开。

## 目标

1. **有周期：** 阶段 + 可否新开为主视觉；仓位/模式次行；inputs 默认折叠「明细」；警告保持醒目。  
2. **无周期：** 说明可 Ops 预热 `warm_market_summary`，并提供「去 Ops」链接。  
3. **阈值入口：** 卡片上「阈值」按钮展开下方判定阈值区（逻辑不变）。

## 非目标

- 改 `build_emotion_cycle` / classify / thresholds 读写 API  
- 无周期时也展示阈值编辑器（方案 B）  
- 市场↔板块联动、改 Redis/连板情绪卡片结构（可顺带不碰）  
- 新图表、阶段时间轴、历史回放

## 决策摘要

| 项 | 选择 |
|----|------|
| 方案 | A：纯前端展示分层 + 空态 Ops 提示 |
| inputs | 默认折叠，按钮切换展开 |
| 阈值区可见条件 | 仍 `v-if="overview?.emotion_cycle"` |
| 判定逻辑 | 不动 |

---

## 1. UI 行为

### 1.1 有 `emotion_cycle`

卡片结构（语义）：

```
情绪周期
[stage_label]  [可新开 | 不宜新开]
仓位建议 x–y% · 模式…
警告行（若有）…
[明细 ▾] / 展开后的 inputs 一行
[阈值]  ← 设置 thresholdsOpen=true，可选 scrollIntoView 到 thresholds-section
```

- 「可新开」/「不宜新开」用 class 区分（如 ok / warn），不引入新颜色体系外的特效。  
- inputs 字段与现网一致：涨停/跌停/最高板/恐贪/MA5。  
- 「阈值」：`thresholdsOpen = true`；若 section 已在 DOM，`querySelector` / ref `scrollIntoView({ behavior: 'smooth', block: 'nearest' })`。

### 1.2 无 `emotion_cycle`（但有 overview）

```
情绪周期
暂无数据
可到 Ops 执行 warm_market_summary 预热。
[去 Ops] → /ops
```

（overview 整段不存在时沿用现有：无 cards 区——不另造 loading 壳，YAGNI。）

### 1.3 判定阈值区

- 仍仅在有 `emotion_cycle` 时渲染。  
- 展开/保存/恢复默认行为不变；卡片「阈值」只负责打开面板。

---

## 2. 模块

| 路径 | 职责 |
|------|------|
| `frontend/src/views/MarketView.vue` | 分层模板、明细折叠、空态链接、阈值快捷 |
| `docs/smoke-checklist.md` | `/market` 情绪展示项 |
| `docs/product-roadmap.md` | 近期待办条目 |

---

## 3. 验收

1. 有周期时首屏可读：阶段与可否新开突出；明细默认收起可展开。  
2. 点「阈值」展开判定阈值区。  
3. 无周期时见 Ops 提示与「去 Ops」。  
4. 阈值保存/恢复仍可用；排行过滤排序不受影响。  
5. `./scripts/check.sh` 绿。

## 4. 风险

- 卡片信息略增按钮密度——「明细」「阈值」保持 ghost/tiny，避免压过阶段主视觉。  
- 无 Redis/warm 时用户仍需手动 Ops；本刀只给路径，不自动触发 job。

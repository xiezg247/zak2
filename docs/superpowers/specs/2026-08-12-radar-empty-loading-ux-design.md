# 雷达首屏 / 空态 UX 设计

日期：2026-08-12  
状态：已批准（方案 A：纯前端；加载提示 + 无卡片空态 + 共振空态）  
范围：仅 zak2 `RadarView`；不改雷达 API / warm job / 展望引擎

## 背景

雷达页已有卡片网格、详情、共振侧栏、权重、次日草案。`loading` 仅禁用刷新按钮；`cards` 为空时主区空白；共振空态文案偏含糊。Ops 有 `warm_radar_card_snapshots` 可预热，页上无引导。

## 目标

1. `loading` 时工具条显示「加载中…」。  
2. 无卡片且非 loading/非 error：主区空态 + 链到 `/ops`。  
3. 共振侧栏空态文案更明确（≥2 卡命中）。  
4. 不改卡片数据、权重、草案、Hub 跳转逻辑。

## 非目标

- 实现 `scan_horizon_outlook` / 展望读路径  
- 改 `warm_radar_card_snapshots` job  
- 骨架屏动画、卡片排序过滤

## 决策摘要

| 项 | 选择 |
|----|------|
| 方案 | A：纯前端 |
| 无卡片引导 | 文案 + `RouterLink` 去 Ops |
| 空态条件 | `!loading && !error && cards.length===0` |

---

## 1. UI

### 1.1 工具条

在刷新按钮附近：

```html
<span v-if="loading" class="muted">加载中…</span>
```

### 1.2 主区无卡片

在 `grid` 外或替代空 grid：

```html
<p v-if="!loading && !error && !cards.length" class="muted empty-main">
  暂无雷达卡片。可点刷新，或于 Ops 手动执行 warm_radar_card_snapshots 预热缓存。
  <RouterLink to="/ops" class="draft-link">去 Ops</RouterLink>
</p>
```

有卡片时仍渲染现有 `grid` + `detail`。

### 1.3 共振空态

原文：`暂无共振（刷新雷达卡片后再试）`  

改为：`暂无共振标的（需至少 2 张卡片命中同一标的；可调权重后刷新）`

## 2. 模块

| 路径 | 职责 |
|------|------|
| `frontend/src/views/RadarView.vue` | 上述三处 UI + 少量样式 |
| `docs/smoke-checklist.md` | 雷达空态/加载检查项 |
| `docs/product-roadmap.md` | 完成项 |

## 3. 验收

1. 刷新过程可见「加载中…」。  
2. 无卡片时见空态并可进 Ops。  
3. 无共振时见新侧栏文案。  
4. 有数据时卡片/共振/权重/草案不变。  
5. `./scripts/check.sh` 绿。

## 明确不做

展望引擎；改 warm job；骨架屏；卡片排序过滤。

# 雷达展望读路径薄壳设计

日期：2026-08-12  
状态：已批准（方案 A：纯前端折叠面板；不读 cache、不新增 API）  
范围：仅 zak2 `RadarView`；不实现 horizon/predict 管线

## 背景

Ops 有 `scan_horizon_outlook`（恒 skipped）；PG 有 `radar_horizon_cache` / `radar_predict_cache`，但无读 API、无 Web 入口。用户在雷达页找不到「展望」能力边界说明。

## 目标

1. 雷达页增加可折叠「展望」区（默认折叠，标注「暂不可用」）。  
2. 展开后诚实说明：管线未接入；Ops job 为占位；链到 `/ops`。  
3. 不读空表、不伪造数据、不新增 GET API。  
4. 不改卡片 / 共振 / 权重 / 草案。

## 非目标

- 实现扫描引擎或写 cache  
- `GET /radar/horizon`  
- 伪造展望列表  
- 改 `scan_horizon_outlook` job 行为

## 决策摘要

| 项 | 选择 |
|----|------|
| 方案 | A：纯前端 |
| 默认 | 折叠 |
| 数据 | 无请求 |

---

## 1. UI

**位置：** 工具条与 `.body` 之间（`error` / `draftMsg` 之后）。

**状态：** `horizonOpen = ref(false)`

**结构：**

```html
<div class="horizon-block">
  <div class="horizon-head">
    <strong>展望</strong>
    <span class="muted">暂不可用</span>
    <button type="button" class="ghost tiny-btn" @click="horizonOpen = !horizonOpen">
      {{ horizonOpen ? '收起' : '展开' }}
    </button>
  </div>
  <div v-if="horizonOpen" class="horizon-panel muted">
    <p>
      zak2 尚未接入雷达展望扫描管线（horizon / predict），当前无展望数据可读。
      Ops 中的 scan_horizon_outlook 为可跑占位（恒 skipped），待管线落地后再展示结果。
    </p>
    <RouterLink to="/ops" class="draft-link">去 Ops</RouterLink>
  </div>
</div>
```

样式对齐行业/权重折叠头（flex 横排）；`.horizon-panel` 少量 padding。

## 2. 模块

| 路径 | 职责 |
|------|------|
| `frontend/src/views/RadarView.vue` | 面板 |
| `docs/smoke-checklist.md` | 检查项 |
| `docs/product-roadmap.md` | 完成项 |

## 3. 验收

1. 可见「展望 · 暂不可用」，可展开收起。  
2. 文案含管线未接入与 `scan_horizon_outlook`；可进 Ops。  
3. 卡片/共振/权重/草案不变。  
4. `./scripts/check.sh` 绿。

## 明确不做

引擎；读/写 cache；GET API；伪造数据。

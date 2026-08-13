# 雷达详情反馈清空与操作钮样式 UX 设计

日期：2026-08-13  
状态：已批准（方案 A：清 detailMsg + 详情钮改用 tiny-btn）  
范围：仅 zak2 `RadarView`；修 #39 终审 Minor；不改 API / 加自选逻辑

## 背景

#39 落地后终审指出：切换卡片时 `detailMsg` 残留；详情操作使用 `class="tiny"` 与文本工具类冲突，按钮 chrome 偏弱。侧栏权重已有 `.tiny-btn`。

## 目标

1. 换卡或整页 `load` 时清空 `detailMsg`。  
2. 详情三钮改用 `.tiny-btn`（不污染文本 `.tiny`）。  
3. 更新 smoke 与路线图 #40。

## 非目标

- 改 `addWatchTo` / 跳转路径 / 共振侧栏行为  
- 大改视觉体系、全局重命名 `.tiny`

## 决策摘要

| 项 | 选择 |
|----|------|
| 方案 | A |
| 清空时机 | `load()` + `watch(activeId)` |
| 按钮 class | `tiny-btn`（复用现有） |

---

## 1. UI / 行为

### 1.1 清 detailMsg

- `load()` 中与 `sideMsg.value = ''` 同处：`detailMsg.value = ''`  
- 增加：

```typescript
watch(activeId, () => {
  detailMsg.value = ''
})
```

### 1.2 按钮

详情操作列三个 `button`：`class="tiny"` → `class="tiny-btn"`（保留 `row-actions` 容器）。  
无需新建按钮样式，除非复用后仍不可点——则仅 `.row-actions .tiny-btn` 微调，本刀以复用为准。

---

## 2. 模块

| 路径 | 职责 |
|------|------|
| `frontend/src/views/RadarView.vue` | watch / load 清空；class 调整 |
| `docs/smoke-checklist.md` | 切换卡片后详情反馈清空 |
| `docs/product-roadmap.md` | #40 |

---

## 3. 验收

1. 加自选出反馈后切换卡片，详情区反馈消失。  
2. 刷新/`load` 后 `detailMsg` 为空。  
3. 详情三钮外观接近侧栏权重小按钮；文本 `.tiny` 未变。  
4. smoke + roadmap 已更新。

## 风险

无。

# Feed「仅启用」订阅过滤 UX 设计

日期：2026-08-13  
状态：已批准（方案 A：纯前端；enabledOnly 默认关；保持 subId）  
范围：仅 zak2 `FeedView`；不改 Feed API / 批量已读 / 页内同步

## 背景

`/feed` 左侧已有 #35 文本过滤（名/mid）与开/关订阅。已关订阅仍占列表；右侧已有「仅未读」。#35 非目标含「仅启用」过滤——本刀补齐。

## 目标

1. 左侧可选「仅启用」，默认关。  
2. 与文本过滤组合：先 `enabled`，再 `subFilter`。  
3. 滤掉当前选中时保持 `subId`。  
4. 更新 smoke 与路线图 #37。

## 非目标

- 改 Feed API  
- 批量已读、页内强制同步  
- 改右侧 `listFilter` / `unreadOnly`  
- 过滤时自动清空 `subId`  
- 默认开启「仅启用」

## 决策摘要

| 项 | 选择 |
|----|------|
| 方案 | A：并入 `displayedSubs` |
| `enabledOnly` 默认 | `false` |
| 管道 | `subs` → enabled 过滤（可选）→ 文本过滤 → 列表 |
| 「全部」 | 始终可见 |
| 选中被滤掉 | 保持 `subId` |

---

## 1. UI 行为

### 1.1 控件

- `subs.length > 0` 时：现有 `subFilter` 旁或下方增加  
  `<label class="…"><input type="checkbox" v-model="enabledOnly" /> 仅启用</label>`  
  （样式可对齐右侧 `unread-label`）

### 1.2 displayedSubs

```
subs
  → enabledOnly ? filter(s => s.enabled) : all
  → subFilter trim/lower：display_name / source_id includes
  → displayedSubs
```

### 1.3 空态

| 条件 | 左侧 |
|------|------|
| `subs.length && !displayedSubs.length` | 过滤控件 +「全部」+「无匹配订阅」 |
| 其它 | 现有（#35） |

右侧时间线 / `subId` 行为不变。

---

## 2. 模块

| 路径 | 职责 |
|------|------|
| `frontend/src/views/FeedView.vue` | `enabledOnly`、管道、样式 |
| `docs/smoke-checklist.md` | `/feed` 验收 |
| `docs/product-roadmap.md` | #37 |

---

## 3. 验收

1. 默认可见全部订阅；勾选「仅启用」后只列已开。  
2. 可与名/mid 文本过滤叠加；无匹配见「无匹配订阅」。  
3. 滤掉当前选中时右侧仍按该 `subId`。  
4. 「全部」始终可见；右侧仅未读等不变。  
5. smoke + roadmap 已更新。

## 风险

无；纯前端列表过滤。

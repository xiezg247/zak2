# 雷达卡片列表：source 筛选 + 过滤 + 排序 设计

日期：2026-08-12  
状态：已批准（方案 A：纯前端 `displayedCards` 管道）  
范围：仅 zak2 `RadarView` 卡片网格；不改雷达 API / 共振 / 展望

## 背景

雷达卡片网格直接 `v-for="cards"`，无法按来源筛选、按标题过滤或排序。字段已有 `title` / `subtitle` / `source` / `rows.length`。

## 目标

1. source chips（全部 + 去重 source）筛选。  
2. 文本过滤：`title` / `subtitle` / `source`。  
3. 排序：默认序 / 标题 / 行数（升↔降）。  
4. 空态区分真无卡 vs 过滤无匹配；`active` 跟随 `displayedCards`。  
5. 不改 API、共振、展望、权重、草案。

## 非目标

- 后端筛选参数  
- 卡片拖拽排序  
- 改 warm job

## 决策摘要

| 项 | 选择 |
|----|------|
| 方案 | A：纯前端管道 |
| 排序默认方向 | 标题/行数首次为降序，再点切换 |
| 过滤条显示 | 仅 `cards.length > 0` |

---

## 1. 管道

```
cards
  → sourceChip === '' ? all : source === sourceChip
  → query match title|subtitle|source (case-insensitive)
  → sort (null | title | rows)
  → displayedCards
```

## 2. 状态

```typescript
const cardFilter = ref('')
const sourceChip = ref('') // '' = 全部
const cardSortKey = ref<'title' | 'rows' | null>(null)
const cardSortDir = ref<'asc' | 'desc'>('desc')
```

- `sourceOptions = computed(() => unique sorted sources from cards)`  
- `displayedCards = computed(...)`  
- `toggleCardSort(key)` / `clearCardSort()`  
- `watch(displayedCards, ...)`：若 `activeId` 不在列表 → `displayedCards[0]?.card_id ?? ''`

## 3. UI

有卡片时，grid 上方：

1. chips：`全部` + 各 source（`:class="{ on: sourceChip === s }"`）  
2. input：`过滤标题/来源`  
3. 「默认序」「标题」「行数」控件（带 ▲/▼ 标记）

网格：`v-for="c in displayedCards"`。

空态：

| 条件 | UI |
|------|-----|
| `!loading && !error && !cards.length` | 现有 empty-main（去 Ops） |
| `cards.length && !displayedCards.length` | 过滤条 +「无匹配卡片」 |

## 4. 模块

| 路径 | 职责 |
|------|------|
| `frontend/src/views/RadarView.vue` | 管道 + UI |
| `docs/smoke-checklist.md` | 检查项 |
| `docs/product-roadmap.md` | 完成项 |

## 5. 验收

1. source chip 与文本过滤生效；标题/行数可排序。  
2. 无匹配见「无匹配卡片」；真无卡仍见 Ops 空态。  
3. 过滤后详情跟随可见首卡或清空。  
4. 共振/展望/权重/草案不变。  
5. `./scripts/check.sh` 绿。

## 明确不做

后端筛选；拖拽；改 warm/展望管线。

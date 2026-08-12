# 自选列表列偏好设计

日期：2026-08-12  
状态：已批准（方案 A：列勾选 + localStorage；不改后端）  
范围：仅 zak2 `WatchlistView` 自选列表表；不改分组/策略看盘/持仓表

## 背景

自选列表已扩列并排序过滤；列全部固定展示，窄屏/噪声时无法隐藏次要列。先前扩列 spec 明确将「列勾选偏好」列为非目标，本刀补齐。

## 目标

1. 可选列可开关：行业、换手%、量比、成交额（默认全开）。  
2. 核心列始终显示：代码、名称、现价、涨幅%、删。  
3. 偏好写入本机 `localStorage`，刷新后保留。

## 非目标

- 用户 prefs API / 跨设备同步  
- 列拖拽重排、列宽记忆  
- 分组排序、批量移组  
- 策略看盘 / 持仓表列偏好

## 决策摘要

| 项 | 选择 |
|----|------|
| 方案 | A：过滤条旁「列」面板 + checkbox |
| 存储 | `localStorage` 键 `zak2:watchlist:list_columns` |
| 可关列 | `industry` / `turnover_rate` / `volume_ratio` / `amount` |
| 隐藏后排序 | 若 `sortKey` 落在隐藏列 → 清为默认序 |

---

## 1. UI 行为

### 1.1 入口

- 列表工具区（过滤框 /「默认序」旁）增加按钮「列」。  
- 点击切换 `columnsOpen`；展开为勾选列表（四项中文标签：行业、换手%、量比、成交额）。  
- 再点「列」收起；YAGNI：可不做点击外部关闭（可选实现，非必须）。

### 1.2 显隐

- `v-if="colVisible.industry"` 等控制对应 `<th>` / `<td>`。  
- `colspan` 空态行随可见列数调整（或用足够大的固定 colspan，避免错位——推荐按可见列数计算）。

### 1.3 持久化

```json
{
  "industry": true,
  "turnover_rate": true,
  "volume_ratio": true,
  "amount": true
}
```

- 挂载时 `JSON.parse(localStorage.getItem(...))`，与默认 merge（未知键忽略，缺键用 true）。  
- 勾选变更：更新 reactive 状态并 `setItem`。  
- parse 失败：回退全 true。

### 1.4 与排序交互

- 用户关闭某可选列且 `sortKey === 该列` 时调用现有 `clearSort()`。  
- 过滤、选中保留、日 K、删除逻辑不变。

---

## 2. 模块

| 路径 | 职责 |
|------|------|
| `frontend/src/views/WatchlistView.vue` | 列面板、显隐、localStorage |
| `docs/smoke-checklist.md` | 自选列偏好检查项 |
| `docs/product-roadmap.md` | 近期待办条目 |

---

## 3. 验收

1. `/watchlist` 可关闭可选列，刷新后仍关闭；可再打开。  
2. 代码/名称/现价/涨幅%/删始终可见。  
3. 关闭正在排序的列时回到默认序。  
4. 过滤与行选中仍可用。  
5. `./scripts/check.sh` 绿。

## 4. 风险

- 清站点数据会丢偏好——本机存储预期行为。  
- 多标签页不同步——YAGNI（后打开的页以各自读写为准，或靠 storage 事件；本刀不做跨 tab 同步）。

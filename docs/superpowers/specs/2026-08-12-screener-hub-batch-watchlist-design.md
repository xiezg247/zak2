# 选股 Hub 批量入自选设计

日期：2026-08-12  
状态：已批准（方案 1：勾选 + 串行现有 POST；操作 displayedRows）  
范围：仅 zak2 `ScreenerHubView`；不新增批量 API

## 背景

结果表仅有单行「自选」→ `watchlistApi.add`。缺多选与一键批量加入。自选上限 50；重复加入返回 409「已在自选中」。

## 目标

1. 结果表勾选列 + 表头全选当前 `displayedRows`。  
2. 「加入自选 (N)」对已勾选串行调用现有 `add`；汇总成功 / 已在自选 / 失败。  
3. 单行「自选」保留。  
4. 打开新 run 清空勾选；过滤变化时 prune 不可见项。  
5. 不改后端。

## 非目标

- `POST /watchlist/batch`  
- 写入分组  
- 改 `WATCHLIST_MAX`  
- 改排序/过滤/历史逻辑（仅挂钩清空勾选）

## 决策摘要

| 项 | 选择 |
|----|------|
| API | 串行现有 `POST /watchlist` |
| 409 | 计为「已在自选」，继续 |
| 其它错误 | 计失败，继续下一条 |
| 全选范围 | `displayedRows` |
| Vue Set | 用响应式 `Set` 或 `Record<string, true>`（实现选可维护者） |

---

## 1. 状态与辅助

```typescript
const selectedVts = ref<Record<string, true>>({}) // 推荐 Record 保证响应式
const batchBusy = ref(false)

function rowVt(row: Record<string, unknown>): string {
  return String(row.vt_symbol || row.symbol || '').trim()
}
```

- `selectedCount`：勾选中且（可选）仍合理的数量。  
- `toggleVt(vt)` / `toggleSelectAllDisplayed()` / `clearSelected()`。  
- `allDisplayedSelected`：`displayedRows` 非空且全部在 selected。

## 2. UI

- 表头首列 checkbox；行首列 checkbox（`@click.stop`）。  
- 结果工具条（过滤行旁）增加：

`加入自选 ({{ selectedCount }})` — `selectedCount===0` 或 `batchBusy` 时 disabled；busy 文案「加入中…」。

- 空行 `colspan`：16 → 17。

## 3. 批量逻辑

对每个选中 vt（顺序稳定：按 `displayedRows` 顺序遍历并过滤 selected）：

1. `watchlistApi.add(vt, name)`  
2. 成功 → ok++  
3. `message` 包含 `已在自选中` → skip++  
4. 其它 → fail++  

结束：

```
statusText = `已加入 ${ok} · 已在自选 ${skip} · 失败 ${fail}`
```

若 `fail > 0`，可同时 `error = '部分加入失败，见上方汇总'`（或仅 statusText）。

## 4. 勾选生命周期

| 事件 | 行为 |
|------|------|
| `openRun` 成功 / `pollJob` 写入新 `current` | `clearSelected()` |
| `displayedRows` 变化（过滤/排序） | prune：去掉不在当前 displayed 的 vt（排序不变集合时可仅过滤时 prune——**过滤或 rows 源变化时 prune**） |

实现建议：`watch(displayedRows, ...)` prune，或 `watch(() => current.value?.id)` 清空。

## 5. 文档

- smoke：勾选 / 全选 / 批量汇总 / 单行自选仍可用  
- roadmap：记完成项 #15

## 6. 验收

1. 可勾选与全选当前过滤结果。  
2. 批量后见「已加入 / 已在自选 / 失败」汇总。  
3. 切换历史 run 后勾选清空。  
4. 单行自选、排序过滤、导出、历史不变。  
5. `./scripts/check.sh` 绿。

## 明确不做

批量 API；入组；改上限；后端改动。

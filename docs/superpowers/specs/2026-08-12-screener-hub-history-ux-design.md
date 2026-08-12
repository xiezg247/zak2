# 选股 Hub 运行历史打磨设计

日期：2026-08-12  
状态：已批准（方案 A：纯前端；空态/高亮/加载错误 + diff 展开）  
范围：仅 zak2 `ScreenerHubView` 历史区与结果 diff；不改 runs API

## 背景

Hub 左侧有运行历史列表，结果区有相对上次的 `diff` 计数。缺口：无空态、无当前高亮、打开/加载无错误反馈，`diff` 不能展开看具体代码。

## 目标

1. 历史为空时显示明确空态。  
2. 当前打开的 run 在历史列表高亮（复用 `.hist.on`）。  
3. `loadHistory` / `openRun` 有 busy 与失败文案。  
4. `diff` 可展开列出新增/移除代码；点代码写入结果过滤框。  
5. 历史区可手动刷新。  
6. 不改 runs API、不删历史。

## 非目标

- DELETE run / 双 run 选择对比  
- 改 diff 计算逻辑  
- 批量入自选  
- 展开 `kept` 全量列表

## 决策摘要

| 项 | 选择 |
|----|------|
| 方案 | A：纯前端 |
| 打开历史 | 清 `resultFilter` |
| loadHistory 失败 | 保留旧列表 + `historyErr` |
| kept | 仅计数，不展开 |

---

## 1. 状态

| ref | 用途 |
|-----|------|
| `historyBusy` | loadHistory / 刷新 |
| `runBusy` | openRun |
| `historyErr` | 历史加载错误 |
| `showDiffDetail` | diff 展开 |

## 2. 行为

### 2.1 历史列表

- 标题旁「刷新」按钮：调用 `loadHistory`；`historyBusy` 时禁用。  
- 空态（非 busy 且无 err）：`暂无运行记录，点上方「运行」生成`。  
- 项：`:class="{ on: current?.id === h.id }"`。  
- `loadHistory`：try/catch；成功清 `historyErr`；失败设 `historyErr`，**不**清空已有 `history`。

### 2.2 openRun(id)

- 设 `runBusy`；成功：`current = detail`，`resultFilter = ''`，可选 `showDiffDetail = false`。  
- 失败：写入 `error`（与页级错误一致）。  
- finally 清 `runBusy`。

### 2.3 diff

- 有 `diff` 时显示计数；提供可点控件（如「详情」或整行）toggle `showDiffDetail`。  
- 展开：`新增` chips ← `diff.added`；`移除` chips ← `diff.removed`。  
- 点 chip：`resultFilter = 该代码字符串`。  
- `kept` 仅保留计数文案，不列 chips。

## 3. 模块

| 路径 | 职责 |
|------|------|
| `frontend/src/views/ScreenerHubView.vue` | UI + 上述逻辑 |
| `docs/smoke-checklist.md` | Hub 历史检查项 |
| `docs/product-roadmap.md` | 完成项 |

## 4. 验收

1. 无历史见空态；可刷新。  
2. 打开某条后该条高亮。  
3. 打开/加载失败有错误提示。  
4. 有 diff 时可展开新增/移除并点选写入过滤。  
5. 运行 / 导出 / 结果排序过滤不变。  
6. `./scripts/check.sh` 绿。

## 明确不做

后端 DELETE；双 run 对比；改 engine diff；批量入自选。

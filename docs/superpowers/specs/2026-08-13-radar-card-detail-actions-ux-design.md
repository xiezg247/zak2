# 雷达卡片详情行操作 UX 设计

日期：2026-08-13  
状态：已批准（方案 A：详情表操作列；加自选 + 在自选打开 + 去笔记）  
范围：仅 zak2 `RadarView` 卡片详情表；不改 radar API / 共振侧栏 / 展望

## 背景

`/radar` 卡片详情为只读表；共振侧栏已有「加自选」。市场排行详情已有加自选 / 在自选打开。卡片行无法一键落自选或跳转笔记。

## 目标

1. 详情表对可解析 `vt` 的行提供：加自选、在自选打开、去笔记。  
2. 加自选复用现有 `addWatch`；详情区独立反馈。  
3. 无 vt 行（如纯板块）不显示操作按钮。  
4. 更新 smoke 与路线图 #39。

## 非目标

- 改 radar / watchlist API  
- 卡片网格操作、共振侧栏改版、展望行操作、批量加当前卡  
- 详情表行过滤

## 决策摘要

| 项 | 选择 |
|----|------|
| 方案 | A：操作列三钮 |
| vt 解析 | `vt_symbol` → `tf_symbol` → `symbol` 首个非空 |
| 反馈 | 独立 `detailMsg`（不与 `sideMsg` 混用） |
| 无 vt | 操作列显示「—」 |

---

## 1. UI 行为

### 1.1 解析

```typescript
function rowVt(row: Record<string, unknown>): string {
  for (const k of ['vt_symbol', 'tf_symbol', 'symbol'] as const) {
    const v = String(row[k] || '').trim()
    if (v) return v
  }
  return ''
}
```

名称：`String(row.name || '').trim()` 或回退 `rowLabel` 中非 sector 部分；加自选传 `name || ''`。

### 1.2 详情表

- `<th>操作</th>`  
- 有 `vt`：三个 `button.tiny`（或 ghost tiny）  
  - 加自选：`@click="addWatchFromDetail(vt, name)"`，`:disabled="actingVt === vt"`  
  - 在自选打开：`router.push({ path: '/watchlist', query: { symbol: vt } })`  
  - 去笔记：`router.push({ path: '/notes', query: { symbol: vt } })`  
- 无 `vt`：`—`

### 1.3 反馈

- `detailMsg` ref；详情 `h2` 下 `<p v-if="detailMsg">`  
- `addWatchFromDetail`：可包一层写 `detailMsg`，或扩展 `addWatch` 增加可选 target；**推荐**薄封装调用现有 `addWatch` 逻辑并写 `detailMsg`（避免侧栏也被污染——若复用 `addWatch` 现写 `sideMsg`，则改为写双方或抽公共并分别赋值；**本刀要求详情操作用 `detailMsg`**）

建议实现：

```typescript
async function addWatchTo(vt: string, name: string | undefined, msgRef: typeof detailMsg) {
  // 同现 addWatch，但写入 msgRef
}
```

侧栏继续用 `sideMsg`；详情用 `detailMsg`。

### 1.4 空行

`!active.rows.length` 空态 colspan 改为 4。

---

## 2. 模块

| 路径 | 职责 |
|------|------|
| `frontend/src/views/RadarView.vue` | 操作列、`rowVt`、`detailMsg`、跳转 |
| `docs/smoke-checklist.md` | `/radar` 详情行操作验收 |
| `docs/product-roadmap.md` | #39 |

---

## 3. 验收

1. 有 vt 的详情行可见三钮；加自选成功/失败在详情区可见提示。  
2. 「在自选打开」「去笔记」分别进入带 `symbol` 的对应页。  
3. 无 vt 行操作列为「—」；共振侧栏、卡片过滤、展望不变。  
4. smoke + roadmap 已更新。

## 风险

部分卡片行字段不统一；无 vt 时静默「—」可接受。

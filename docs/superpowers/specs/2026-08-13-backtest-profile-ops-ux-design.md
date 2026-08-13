# 回测画像填参与失败 Ops 引导设计

日期：2026-08-13  
状态：已批准（方案 A：扩 PROFILES 数值字段 + chip 填参 + 错误链 Ops）  
范围：zak2 backtest profiles API + `BacktestView`；不改双均线引擎核心逻辑

## 背景

#33 已做历史过滤空态。画像 chip 只读展示；API 无快慢均线/资金。日 K 不足时错误已指向 Ops 文案，页内无跳转。

## 目标

1. `PROFILES` / `StrategyProfileOut` 增加 `fast_window`、`slow_window`、`capital`。  
2. 点 chip 写入表单三字段并高亮当前画像；不自动开跑。  
3. 失败文案匹配「日 K|Ops|补全」时旁挂去 Ops 链接。  
4. 更新 smoke 与路线图 #34。

## 非目标

- 改回测撮合/统计公式  
- 自动改日期、标的、策略 id  
- Ops 深链自动执行 `fill_watchlist_bars`  
- 画像持久化到用户偏好

## 决策摘要

| 项 | 选择 |
|----|------|
| 方案 | A |
| 初值 | ultra_short 3/8；short_swing 5/20；medium_watch 10/30；trend 20/60；capital 均 100000 |
| chip | 可点；高亮 `activeProfileId` |
| Ops 链 | `RouterLink` → `/ops`，文案「去 Ops 补全日 K」 |

---

## 1. 后端

### 1.1 PROFILES

每项增加：

```python
"fast_window": int,
"slow_window": int,
"capital": float,
```

约束：`2 ≤ fast < slow ≤ 250`；`capital > 0`（与请求 Field 一致）。

### 1.2 Schema

`StrategyProfileOut` 增加三字段。

### 1.3 测试

- `GET` profiles（或直接测 `PROFILES` / schema dump）含三字段；`fast_window < slow_window`。

---

## 2. 前端 BacktestView

### 2.1 类型

`StrategyProfile` 增加 `fast_window` / `slow_window` / `capital`。

### 2.2 chip

```ts
function applyProfile(p: StrategyProfile) {
  fast.value = p.fast_window
  slow.value = p.slow_window
  capital.value = p.capital
  activeProfileId.value = p.profile_id
}
```

- `button.chip` + `@click`；`:class="{ on: activeProfileId === p.profile_id }"`。  
- 用户手改 fast/slow/capital 后可不强制清 `activeProfileId`（YAGNI：可清可不清；**推荐手改不清**，避免打扰）。

### 2.3 失败引导

```vue
<p v-if="error" class="err">
  {{ error }}
  <RouterLink
    v-if="/日 K|Ops|补全/.test(error)"
    to="/ops"
    class="draft-link"
  >去 Ops 补全日 K</RouterLink>
</p>
```

---

## 3. 模块

| 路径 | 职责 |
|------|------|
| `backend/app/services/backtest_engine.py` | PROFILES 数值 |
| `backend/app/schemas/backtest.py` | StrategyProfileOut |
| `backend/tests/…` | profiles 字段测 |
| `frontend/src/api/backtest.ts` | 类型 |
| `frontend/src/views/BacktestView.vue` | chip + Ops 链 |
| `docs/smoke-checklist.md` / `product-roadmap.md` | #34 |

---

## 4. 验收

1. `/api/v1/backtest/profiles` 返回含 fast/slow/capital。  
2. 点「趋势」等 chip，表单三字段变为对应值并高亮。  
3. 人为触发日 K 不足错误时，可见「去 Ops 补全日 K」链到 `/ops`。  
4. 不自动开始回测。  
5. smoke + roadmap 已更新。

## 风险

画像初值为启发式，非实盘最优；description 与数值可后续再调。

# 看盘入队回测 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** 策略看盘「入队回测」：confirm 后调用现有回测 API 入队，跳转 `/backtest?job_id=` 轮询；「同参回测」仍只预填。

**Architecture:** 抽取纯函数参数映射（模式→策略/窗口/ADX）；Watchlist 双按钮；BacktestView 读 `job_id` 复用 `pollJob`，不因 job_id 再 `start`。

**Tech Stack:** Vue 3、既有 `backtestApi` / `jobsApi`、FastAPI（不改协议）

**Spec:** `docs/superpowers/specs/2026-08-14-strategy-board-enqueue-backtest-design.md`

## Global Constraints

- 只改 zak2；不下单；不改 CTA / ARQ 协议
- 「同参回测」不得自动开跑
- 入队固定 `interval=d`；区间 `2020-01-01`～`2026-06-01`；资金 `100000`
- heuristic / double_ma → `double_ma`；trend_ma → `trend_ma` + ADX 默认
- 不新建专用入队 API
- commit 简体中文；`./scripts/check.sh` 绿
- 前端无 vitest：纯函数用 Node 断言脚本验证；UI 以 `npm run build` 为绿线

## File map

| 路径 | 职责 |
|------|------|
| `frontend/src/lib/boardBacktestParams.ts` | 纯函数：解析窗口、query、入队 body |
| `frontend/scripts/check-board-backtest-params.mjs` | 对纯函数断言（Node） |
| `frontend/src/views/WatchlistView.vue` | 同参改用 helper；入队按钮 |
| `frontend/src/views/BacktestView.vue` | `job_id` → `pollJob` |
| docs | #55、smoke、spec 状态 |

---

### Task 1: 参数映射纯函数

**Files:**
- Create: `frontend/src/lib/boardBacktestParams.ts`
- Create: `frontend/scripts/check-board-backtest-params.mjs`
- Modify: `frontend/package.json`（可选加 script `check:board-bt`）

**Interfaces:**

```ts
export type BoardSignalMode = 'heuristic_v2' | 'double_ma' | 'trend_ma'

export const BOARD_BT_START = '2020-01-01'
export const BOARD_BT_END = '2026-06-01'
export const BOARD_BT_CAPITAL = 100000

export function parseFastSlowFromConfigKey(ck: string): { fast: number; slow: number }
// 失败 → { fast: 5, slow: 20 }

export function buildAlignedBacktestQuery(
  mode: BoardSignalMode,
  vt: string,
  configKey: string,
): Record<string, string>
// trend_ma → strategy/vt/20/60/adx…；否则 double_ma + 解析窗口

export function buildEnqueueRunBody(
  mode: BoardSignalMode,
  vt: string,
  configKey: string,
): Record<string, unknown>
// 含 interval:'d', start/end/capital；trend 带 adx；费用字段不传
```

- [x] **Step 1: 写失败断言脚本**

`frontend/scripts/check-board-backtest-params.mjs`：

```js
import assert from 'node:assert/strict'
import {
  parseFastSlowFromConfigKey,
  buildAlignedBacktestQuery,
  buildEnqueueRunBody,
  BOARD_BT_START,
  BOARD_BT_END,
  BOARD_BT_CAPITAL,
} from '../src/lib/boardBacktestParams.ts'

assert.deepEqual(parseFastSlowFromConfigKey('double_ma:5:10'), { fast: 5, slow: 10 })
assert.deepEqual(parseFastSlowFromConfigKey('bad'), { fast: 5, slow: 20 })

const q = buildAlignedBacktestQuery('trend_ma', '600519.SSE', 'x')
assert.equal(q.strategy, 'trend_ma')
assert.equal(q.fast_window, '20')
assert.equal(q.adx_period, '14')

const body = buildEnqueueRunBody('heuristic_v2', '600519.SSE', 'AshareShortBreakoutStrategy:5:10')
assert.equal(body.strategy, 'double_ma')
assert.equal(body.fast_window, 5)
assert.equal(body.slow_window, 10)
assert.equal(body.interval, 'd')
assert.equal(body.start_date, BOARD_BT_START)
assert.equal(body.end_date, BOARD_BT_END)
assert.equal(body.capital, BOARD_BT_CAPITAL)
assert.equal('rate' in body, false)

console.log('boardBacktestParams ok')
```

（若 Node 无法直接 import `.ts`，改用 `node --experimental-strip-types` 跑脚本，或把 lib 写成 `.mts` 纯 ESM；实现时选能一次跑通的方式，优先 strip-types。）

- [x] **Step 2: Run 确认失败**

```bash
cd frontend && node --experimental-strip-types scripts/check-board-backtest-params.mjs
```

Expected: FAIL（模块不存在）

- [x] **Step 3: 实现 `boardBacktestParams.ts`**

按 Interfaces 实现；`buildAlignedBacktestQuery` 字段与现 `openAlignedBacktest` 一致。

- [x] **Step 4: 断言绿**

```bash
cd frontend && node --experimental-strip-types scripts/check-board-backtest-params.mjs
```

Expected: `boardBacktestParams ok`

- [x] **Step 5: Commit**

```bash
git commit -m "$(cat <<'EOF'
feat(ui): 抽取看盘回测参数映射纯函数

同参预填与入队共用窗口/策略规则。
EOF
)"
```

---

### Task 2: Watchlist「入队回测」

**Files:**
- Modify: `frontend/src/views/WatchlistView.vue`
- Consumes: Task 1 helpers；`backtestApi` from `../api/backtest`

**Interfaces:**
- `resolveBoardVtSymbol(): string` — selected → signals[0] → items[0]
- `openAlignedBacktest()` 改为：`buildAlignedBacktestQuery` + `router.push`
- `enqueueAlignedBacktest()`：
  1. 无 vt → `boardError`，return  
  2. body = `buildEnqueueRunBody(signalMode, vt, board?.config_key || '')`  
  3. `confirm(\`对 ${vt} 入队 ${body.strategy} ${body.fast_window}/${body.slow_window}，区间 ${body.start_date}～${body.end_date}，资金 ${body.capital}？\`)`  
  4. 取消则 return  
  5. `enqueueing=true` → `backtestApi.start(body)` → `router.push({ path:'/backtest', query:{ job_id }})`  
  6. catch → `boardError`；finally `enqueueing=false`
- 模板：同参旁加按钮；`:disabled="enqueueing"`；文案「入队回测」/「入队中…」

- [x] **Step 1: 改 WatchlistView**

```ts
import { backtestApi } from '../api/backtest'
import {
  buildAlignedBacktestQuery,
  buildEnqueueRunBody,
  parseFastSlowFromConfigKey, // 若仅 helper 内用可不导出到 vue
} from '../lib/boardBacktestParams'

const enqueueing = ref(false)

function resolveBoardVtSymbol(): string {
  return (
    selected.value?.vt_symbol ||
    board.value?.signals[0]?.vt_symbol ||
    items.value[0]?.vt_symbol ||
    ''
  )
}

function openAlignedBacktest() {
  const vt = resolveBoardVtSymbol()
  if (!vt) {
    boardError.value = '无可用标的，请先选中自选或等待信号'
    return
  }
  void router.push({
    path: '/backtest',
    query: buildAlignedBacktestQuery(signalMode.value, vt, board.value?.config_key || ''),
  })
}

async function enqueueAlignedBacktest() {
  const vt = resolveBoardVtSymbol()
  if (!vt) {
    boardError.value = '无可用标的，请先选中自选或等待信号'
    return
  }
  const body = buildEnqueueRunBody(signalMode.value, vt, board.value?.config_key || '')
  const ok = window.confirm(
    `对 ${vt} 入队 ${body.strategy} ${body.fast_window}/${body.slow_window}，区间 ${body.start_date}～${body.end_date}，资金 ${body.capital}？`,
  )
  if (!ok) return
  enqueueing.value = true
  boardError.value = ''
  try {
    const { job_id } = await backtestApi.start(body)
    void router.push({ path: '/backtest', query: { job_id } })
  } catch (e) {
    boardError.value = e instanceof Error ? e.message : '入队回测失败'
  } finally {
    enqueueing.value = false
  }
}
```

模板：

```html
<button type="button" class="ghost" @click="openAlignedBacktest()">同参回测</button>
<button
  type="button"
  class="ghost"
  :disabled="enqueueing"
  @click="enqueueAlignedBacktest()"
>
  {{ enqueueing ? '入队中…' : '入队回测' }}
</button>
```

删除 vue 内重复的 `parseFastSlowFromConfigKey` / 手写 query 分支（改走 helper）。

- [x] **Step 2: build**

```bash
cd frontend && npm run build
```

Expected: 成功

- [x] **Step 3: Commit**

```bash
git commit -m "$(cat <<'EOF'
feat(ui): 策略看盘增加入队回测

confirm 后调用既有回测 API 并跳转 job 轮询。
EOF
)"
```

---

### Task 3: BacktestView 消费 `job_id`

**Files:**
- Modify: `frontend/src/views/BacktestView.vue`

**Interfaces:**
- `onMounted`：预填后 `await refresh()`；若 `typeof q.job_id === 'string' && q.job_id.trim()`：
  - `running = true`；`try { await pollJob(id) } catch { error = … } finally { running = false }`
- **禁止**在该分支调用 `backtestApi.start` / `startRun`

- [x] **Step 1: 实现**

```ts
onMounted(async () => {
  const q = route.query
  // …现有预填…
  loading.value = true
  try {
    await refresh()
  } catch (e) {
    error.value = e instanceof Error ? e.message : '加载失败'
  } finally {
    loading.value = false
  }

  const jobId = typeof q.job_id === 'string' ? q.job_id.trim() : ''
  if (!jobId) return
  running.value = true
  error.value = ''
  try {
    await pollJob(jobId)
  } catch (e) {
    error.value = e instanceof Error ? e.message : '回测失败'
  } finally {
    running.value = false
  }
})
```

- [x] **Step 2: build**

```bash
cd frontend && npm run build
```

- [x] **Step 3: Commit**

```bash
git commit -m "$(cat <<'EOF'
feat(ui): 回测页支持 job_id 查询并轮询

承接看盘入队跳转，终态不重复 start。
EOF
)"
```

---

### Task 4: 文档收口

**Files:**
- `docs/product-roadmap.md` — #55  
- `docs/smoke-checklist.md` — 双按钮 / confirm / 轮询  
- `docs/superpowers/specs/2026-08-14-strategy-board-enqueue-backtest-design.md` — 已批准（已实现）  
- 本 plan checklist

- [x] **Step 1: 改文档**

路线图：

```markdown
55. ~~看盘入队回测~~（已完成 → [spec](./superpowers/specs/2026-08-14-strategy-board-enqueue-backtest-design.md)）：双按钮 confirm 入队 + job_id 轮询
```

smoke：同参仍只预填；入队回测 confirm 后跳转并轮询；无标的提示。

- [x] **Step 2: `./scripts/check.sh`**

另跑：`cd frontend && node --experimental-strip-types scripts/check-board-backtest-params.mjs`

Expected: 全绿

- [x] **Step 3: Commit**

```bash
git commit -m "$(cat <<'EOF'
docs(strategy): 记录看盘入队回测完成

更新路线图 #55 与 smoke。
EOF
)"
```

---

## Self-review

1. Spec：双按钮、confirm、start、job_id 轮询、参数映射、同参不变 → Task 1–4。  
2. 无 TBD。  
3. 区间/资金常量与 BacktestView 表单默认一致。

## Execution

建议 worktree：`feat/strategy-board-enqueue-backtest`。

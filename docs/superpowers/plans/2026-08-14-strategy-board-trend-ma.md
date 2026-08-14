# 看盘 trend_ma + 模式偏好 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 看盘第三模式 `trend_ma`（固定 20:60）三轨 warm，UI 切换 + localStorage 记 mode，同参回测预填 trend_ma/ADX。

**Architecture:** 扩展 #53：纯 Python ADX + `compute_trend_ma_signal`；warm 用 OHLC 写 `trend_ma:20:60`；board `signal_mode=trend_ma`；Watchlist 三钮 + localStorage；BacktestView 补 ADX 表单项与 query 预填。

**Tech Stack:** FastAPI、SQLAlchemy、Vue 3、pytest

**Spec:** `docs/superpowers/specs/2026-08-14-strategy-board-trend-ma-design.md`

## Global Constraints

- 只改 zak2；不改 `DoubleMaStrategy` / `TrendMaStrategy` 源码
- 不做请求路径现算；不做看盘入队回测；不做服务端 mode 偏好
- `trend_ma` key 固定 `trend_ma:20:60`；ADX 14/25；trail 0.12 仅预填，不参与看盘判定
- Redis 桥不伪造 `trend_ma:*`
- commit 简体中文；`./scripts/check.sh` 绿

## File map

| 路径 | 职责 |
|------|------|
| `backend/app/services/strategy_signal_ma.py` | ADX + `compute_trend_ma_signal` |
| `backend/tests/test_strategy_signal_ma.py` | 信号单测 |
| `backend/app/services/ops_warm_watchlist_strategy.py` | OHLC 加载 + 第三轨 |
| `backend/tests/test_ops_warm_watchlist_strategy.py` | warm 断言 trend_ma key |
| `backend/app/services/ops_catalog.py` | 三轨文案 |
| `backend/app/services/strategy_board.py` | mode / key / note |
| `backend/tests/test_strategy_board.py` | resolve trend_ma |
| `backend/app/api/v1/watchlist.py` | query 合法值说明（若有） |
| `frontend/src/views/WatchlistView.vue` | 三模式 + localStorage + 预填 |
| `frontend/src/views/BacktestView.vue` | ADX 控件 + query |
| docs | #54、smoke、spec 状态 |

---

### Task 1: `compute_trend_ma_signal` + Wilder ADX

**Files:**
- Modify: `backend/app/services/strategy_signal_ma.py`
- Test: `backend/tests/test_strategy_signal_ma.py`

**Interfaces:**
- Constants: `TREND_MA_FAST=20`, `TREND_MA_SLOW=60`, `TREND_ADX_PERIOD=14`, `TREND_ADX_THRESHOLD=25.0`, `TREND_TRAILING_STOP_PCT=0.12`
- `def wilder_adx(highs, lows, closes, period: int) -> list[float | None]` — 返回与 closes 等长；不足处为 `None`
- `def compute_trend_ma_signal(highs, lows, closes, *, volumes=None, fast=20, slow=60, adx_period=14, adx_threshold=25.0, vt_symbol, as_of) -> dict | None`
- buy / sell / hold 规则见 spec §2；`signal_mode="trend_ma"`；`confirm_bars=0`

- [ ] **Step 1: 写失败测试**

在 `test_strategy_signal_ma.py` 追加：

```python
def test_trend_ma_buy_when_cross_and_adx(monkeypatch) -> None:
    n = 40
    highs = [10.0] * n
    lows = [9.0] * n
    closes = [9.5] * n

    def fake_sma(values: list[float], window: int) -> list[float | None]:
        out: list[float | None] = [None] * len(values)
        if window == 20:
            out[-2], out[-1] = 9.0, 11.0
        else:
            out[-2], out[-1] = 10.0, 10.0
        return out

    monkeypatch.setattr(m, "sma", fake_sma)
    monkeypatch.setattr(m, "wilder_adx", lambda *a, **k: [None] * (n - 1) + [30.0])
    out = m.compute_trend_ma_signal(
        highs, lows, closes, fast=20, slow=60, vt_symbol="600519.SSE", as_of="2026-08-14"
    )
    assert out is not None
    assert out["signal"] == "buy"
    assert out["signal_mode"] == "trend_ma"
    assert out["adx_value"] == 30.0
    assert "追踪止损" in out["reason_summary"] or "不含追踪" in out["reason_summary"]


def test_trend_ma_sell_on_structure_break(monkeypatch) -> None:
    n = 40
    highs = lows = closes = [10.0] * n

    def fake_sma(values: list[float], window: int) -> list[float | None]:
        out: list[float | None] = [None] * len(values)
        # 无交叉；慢线 10，收盘将设为 9 → 破位
        out[-2] = out[-1] = 10.0 if window == 60 else 10.5
        return out

    monkeypatch.setattr(m, "sma", fake_sma)
    monkeypatch.setattr(m, "wilder_adx", lambda *a, **k: [None] * (n - 1) + [10.0])
    closes = [10.0] * (n - 1) + [9.0]
    out = m.compute_trend_ma_signal(
        highs, lows, closes, fast=20, slow=60, vt_symbol="600519.SSE", as_of="2026-08-14"
    )
    assert out is not None
    assert out["signal"] == "sell"
```

- [ ] **Step 2: Run 确认失败**

```bash
cd backend && uv run pytest tests/test_strategy_signal_ma.py::test_trend_ma_buy_when_cross_and_adx -q
```

Expected: FAIL（`wilder_adx` / `compute_trend_ma_signal` 未定义）

- [ ] **Step 3: 实现**

在 `strategy_signal_ma.py` 追加常量与函数（要点）：

```python
TREND_MA_FAST = 20
TREND_MA_SLOW = 60
TREND_ADX_PERIOD = 14
TREND_ADX_THRESHOLD = 25.0
TREND_TRAILING_STOP_PCT = 0.12

def wilder_adx(
    highs: list[float], lows: list[float], closes: list[float], period: int
) -> list[float | None]:
    n = len(closes)
    out: list[float | None] = [None] * n
    if period < 1 or n < period * 2 or len(highs) != n or len(lows) != n:
        return out
    # TR / +DM / -DM
    tr = [0.0] * n
    plus_dm = [0.0] * n
    minus_dm = [0.0] * n
    for i in range(1, n):
        up = highs[i] - highs[i - 1]
        down = lows[i - 1] - lows[i]
        plus_dm[i] = up if up > down and up > 0 else 0.0
        minus_dm[i] = down if down > up and down > 0 else 0.0
        tr[i] = max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]), abs(lows[i] - closes[i - 1]))
    # Wilder 平滑：先 period 和，再递推
    atr = sum(tr[1 : period + 1])
    apdm = sum(plus_dm[1 : period + 1])
    amdm = sum(minus_dm[1 : period + 1])
    dx_vals: list[float | None] = [None] * n
    def _dx(a: float, b: float, t: float) -> float:
        if t <= 0:
            return 0.0
        pdi, mdi = 100.0 * a / t, 100.0 * b / t
        s = pdi + mdi
        return 0.0 if s <= 0 else 100.0 * abs(pdi - mdi) / s
    dx_vals[period] = _dx(apdm, amdm, atr)
    for i in range(period + 1, n):
        atr = atr - atr / period + tr[i]
        apdm = apdm - apdm / period + plus_dm[i]
        amdm = amdm - amdm / period + minus_dm[i]
        dx_vals[i] = _dx(apdm, amdm, atr)
    # ADX = Wilder of DX，从 index 2*period-1 起有值
    first = 2 * period - 1
    if first >= n:
        return out
    seed = [d for d in dx_vals[period : first + 1] if d is not None]
    if len(seed) < period:
        return out
    adx = sum(seed) / period
    out[first] = adx
    for i in range(first + 1, n):
        d = dx_vals[i]
        if d is None:
            continue
        adx = (adx * (period - 1) + d) / period
        out[i] = adx
    return out


def compute_trend_ma_signal(...):  # 签名见 Interfaces
    min_bars = max(slow, adx_period * 2) + 2
    if fast >= slow or len(closes) < min_bars:
        return None
    if len(highs) != len(closes) or len(lows) != len(closes):
        return None
    fast_ma = sma(closes, fast)
    slow_ma = sma(closes, slow)
    adx_arr = wilder_adx(highs, lows, closes, adx_period)
    i, j = len(closes) - 1, len(closes) - 2
    f, s, pf, ps = fast_ma[i], slow_ma[i], fast_ma[j], slow_ma[j]
    adx_v = adx_arr[i]
    if None in (f, s, pf, ps) or adx_v is None:
        return None
    cross = cross_kind(pf, ps, f, s)
    close = closes[i]
    slow_up = s >= ps
    if cross == "buy" and adx_v >= adx_threshold and close > s and slow_up:
        kind = "buy"
    elif cross == "sell" or close < s:
        kind = "sell"
    else:
        kind = "hold"
    # gap / strength / reason（含「不含追踪止损」）/ signal_mode=trend_ma / adx_value
    ...
```

- [ ] **Step 4: 测试绿**

```bash
cd backend && uv run pytest tests/test_strategy_signal_ma.py -q
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git commit -m "$(cat <<'EOF'
feat(strategy): 增加 trend_ma 看盘信号与 Wilder ADX

入场对齐 CTA；无仓卖点不含追踪止损。
EOF
)"
```

---

### Task 2: warm OHLC + 第三轨 `trend_ma:20:60`

**Files:**
- Modify: `backend/app/services/ops_warm_watchlist_strategy.py`
- Modify: `backend/app/services/ops_catalog.py`
- Test: `backend/tests/test_ops_warm_watchlist_strategy.py`

**Interfaces:**
- `_load_daily_bars(...) -> tuple[list[float], list[float], list[float], list[float], str] | None`  
  返回 `(highs, lows, closes, volumes, as_of)`；可保留 `_load_daily_closes` 作薄包装或直接替换并改所有调用/mock 名
- `_compute_pool`：在现有 heuristic/double_ma 循环后（或同循环末），对池内每标的 upsert `trend_ma:20:60`；`limit = min(200, max(TREND_MA_SLOW * 3, TREND_ADX_PERIOD * 4, 80))`
- `message` / catalog 含 `trend_ma` / 三轨

- [ ] **Step 1: 扩展 warm 测试**

在 `test_ops_warm_watchlist_strategy.py` 的 `test_warm_computes_ma_when_bars`（或同名现有用例）中：

```python
patch.object(m, "compute_trend_ma_signal", return_value={..., "signal_mode": "trend_ma"}) as comp_tm,
# _load 返回需含 highs/lows（若改签名）
...
assert any(k == "trend_ma:20:60" for k in ck_args)
assert "trend_ma" in out["message"]
comp_tm.assert_called()
```

同步改 `_load_daily_closes` mock：若函数改名为 `_load_daily_bars`，patch 新名，return  
`([11]*30, [9]*30, [10]*30, [1e5]*30, "2026-08-13")`。

- [ ] **Step 2: 实现 warm + catalog**

```python
from app.services.strategy_signal_ma import (
    ...,
    compute_trend_ma_signal,
    TREND_MA_FAST,
    TREND_MA_SLOW,
    TREND_ADX_PERIOD,
    TREND_ADX_THRESHOLD,
)

# _load_daily_bars: highs/lows from r.high_price / r.low_price

# 在 _compute_pool 末尾（pool 非空）:
tm_key = f"trend_ma:{TREND_MA_FAST}:{TREND_MA_SLOW}"
limit_tm = min(200, max(TREND_MA_SLOW * 3, TREND_ADX_PERIOD * 4, 80))
for symbol, exchange in pool:
    loaded = _load_daily_bars(...)
    ...
    snap = compute_trend_ma_signal(highs, lows, closes, volumes=volumes, ...)
    if snap:
        _upsert_one(vt=vt, config_key=tm_key, as_of=as_of, snap=snap)
```

catalog 描述改为：`… + double_ma + trend_ma 三轨 → watchlist_signal_cache`。

- [ ] **Step 3: 测试绿**

```bash
cd backend && uv run pytest tests/test_ops_warm_watchlist_strategy.py -q
```

- [ ] **Step 4: Commit**

```bash
git commit -m "$(cat <<'EOF'
feat(ops): 策略 warm 写入 trend_ma:20:60 第三轨

日 K 加载 OHLC，切换看盘模式无需现算。
EOF
)"
```

---

### Task 3: board `signal_mode=trend_ma`

**Files:**
- Modify: `backend/app/services/strategy_board.py`
- Modify: `backend/app/api/v1/watchlist.py`（Query description 若写死两模式则扩）
- Test: `backend/tests/test_strategy_board.py`

**Interfaces:**
- `SIGNAL_MODE_TREND_MA = "trend_ma"`
- `def trend_ma_config_key() -> str: return f"trend_ma:{TREND_MA_FAST}:{TREND_MA_SLOW}"`（或字面 `trend_ma:20:60`）
- `resolve_board_config_key`：`mode == trend_ma` → 固定 key
- `load_strategy_board`：合法 mode 集合含 trend_ma；note 含入场对齐 / 不含追踪止损 / 非 vnpy

- [ ] **Step 1: 测试**

```python
def test_resolve_trend_ma_fixed_key(db):
    assert resolve_board_config_key(db, "u1", signal_mode="trend_ma") == "trend_ma:20:60"
```

- [ ] **Step 2: 实现 → 绿**

```bash
cd backend && uv run pytest tests/test_strategy_board.py -q
```

- [ ] **Step 3: Commit**

```bash
git commit -m "$(cat <<'EOF'
feat(api): 策略看盘支持 signal_mode=trend_ma

固定解析 trend_ma:20:60 并更新说明文案。
EOF
)"
```

---

### Task 4: UI 三模式 + localStorage + 回测 ADX 预填

**Files:**
- Modify: `frontend/src/views/WatchlistView.vue`
- Modify: `frontend/src/views/BacktestView.vue`
- （`watchlist.ts` 已传 `signal_mode`，一般无需改）

**Interfaces:**
- `SIGNAL_MODE_KEY = 'zak2:watchlist:signal_mode'`
- `type SignalMode = 'heuristic_v2' | 'double_ma' | 'trend_ma'`
- `loadSignalMode()` / `saveSignalMode(mode)` — 非法回退 heuristic
- `setSignalMode`：赋值 + save + `refreshBoard`
- 挂载：先 `loadSignalMode` 再拉 board
- `openAlignedBacktest`：若 `signalMode === 'trend_ma'` → query  
  `{ strategy:'trend_ma', vt_symbol, fast_window:20, slow_window:60, adx_period:14, adx_threshold:25, trailing_stop_pct:0.12 }`
- BacktestView：`adxPeriod`/`adxThreshold`/`trailingStopPct` refs（默认 14/25/0.12）；`strategy==='trend_ma'` 时显示三输入；`runSingle`/`runBatch`/`runOptimize` body 带这三项；`onMounted` 读 query 预填；**不**调 `startRun`

- [ ] **Step 1: WatchlistView**

```ts
const SIGNAL_MODE_KEY = 'zak2:watchlist:signal_mode'
type SignalMode = 'heuristic_v2' | 'double_ma' | 'trend_ma'
const VALID: SignalMode[] = ['heuristic_v2', 'double_ma', 'trend_ma']

function loadSignalMode(): SignalMode {
  try {
    const v = localStorage.getItem(SIGNAL_MODE_KEY)
    if (v && (VALID as string[]).includes(v)) return v as SignalMode
  } catch { /* ignore */ }
  return 'heuristic_v2'
}

function saveSignalMode(mode: SignalMode) {
  localStorage.setItem(SIGNAL_MODE_KEY, mode)
}

const signalMode = ref<SignalMode>(loadSignalMode())

function setSignalMode(mode: SignalMode) {
  if (signalMode.value === mode) return
  signalMode.value = mode
  saveSignalMode(mode)
  void refreshBoard()
}

function openAlignedBacktest() {
  // ... vt 选取同现逻辑
  if (signalMode.value === 'trend_ma') {
    void router.push({
      path: '/backtest',
      query: {
        strategy: 'trend_ma',
        vt_symbol: vt,
        fast_window: '20',
        slow_window: '60',
        adx_period: '14',
        adx_threshold: '25',
        trailing_stop_pct: '0.12',
      },
    })
    return
  }
  // 现有 double_ma 分支
}
```

模板加第三钮「趋势均线」。

- [ ] **Step 2: BacktestView**

```ts
const adxPeriod = ref(14)
const adxThreshold = ref(25)
const trailingStopPct = ref(0.12)

function trendPayload() {
  if (strategy.value !== 'trend_ma') return {}
  return {
    adx_period: adxPeriod.value,
    adx_threshold: adxThreshold.value,
    trailing_stop_pct: trailingStopPct.value,
  }
}
// start/batch/optimize: ...trendPayload()

// onMounted:
if (typeof q.adx_period === 'string' && Number(q.adx_period) > 0) adxPeriod.value = Number(q.adx_period)
// 同理 threshold / trailing
```

模板：`v-if="strategy === 'trend_ma'"` 三 label。

- [ ] **Step 3: build**

```bash
cd frontend && npm run build
```

Expected: 成功

- [ ] **Step 4: Commit**

```bash
git commit -m "$(cat <<'EOF'
feat(ui): 看盘趋势模式与 localStorage 记 mode

同参回测预填 trend_ma 与 ADX 默认参数。
EOF
)"
```

---

### Task 5: 文档收口

**Files:**
- `docs/product-roadmap.md` — 增 #54 已完成链本 spec  
- `docs/smoke-checklist.md` — 三模式 / localStorage / trend 同参预填  
- `docs/superpowers/specs/2026-08-14-strategy-board-trend-ma-design.md` — 状态 → 已批准（已实现）  
- 本 plan checklist 勾选

- [ ] **Step 1: 改文档**

路线图一行示例：

```markdown
54. ~~看盘 trend_ma + 模式偏好~~（已完成 → [spec](./superpowers/specs/2026-08-14-strategy-board-trend-ma-design.md)）：第三轨 `trend_ma:20:60` + localStorage
```

smoke：看盘三模式可切；刷新保留；趋势模式「同参回测」预填；warm message 含 trend_ma。

- [ ] **Step 2: `./scripts/check.sh`**

Expected: pytest 全绿 + frontend build OK

- [ ] **Step 3: Commit**

```bash
git commit -m "$(cat <<'EOF'
docs(strategy): 记录看盘 trend_ma 与模式偏好完成

更新路线图 #54 与 smoke。
EOF
)"
```

---

## Self-review

1. Spec：信号、warm OHLC、resolve、UI/localStorage、ADX 预填、#54 → Task 1–5。  
2. 无 TBD。  
3. key / mode 命名与 #53 一致；trail 仅预填。

## Execution

建议 worktree 分支：`feat/strategy-board-trend-ma`。

# trend_ma 第二策略 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 zak2 回测中新增日 K 策略 `trend_ma`（双均线 + ADX + 追踪止损），单票/批量可选并可跑。

**Architecture:** 独立 CTA 类注册进现有 vnpy 回测管线；repo 按策略组装 setting；日 K 最低根数对 `trend_ma` 提高；UI 靠 `/strategies` 自动出现。

**Tech Stack:** vnpy / vnpy_ctastrategy、FastAPI、Vue 3、pytest

**Spec:** `docs/superpowers/specs/2026-08-14-backtest-trend-ma-design.md`

## Global Constraints

- 只改 zak2；禁止 import `vnpy_ashare` / zak 策略包
- 语义对齐桌面 `AshareTrendMaStrategy`（只读参考）
- 默认：fast=20, slow=60, adx_period=14, adx_threshold=25.0, trailing_stop_pct=0.12, trade_volume=100
- 最低日 K：`max(30, slow_window + adx_period * 2 + 5)`（默认约 93）
- 不新增画像 chip；优化网格不扩 ADX/止损输入
- commit message 简体中文：`<type>(<scope>): <简述>`
- `./scripts/check.sh` 最终绿

## File map

| 路径 | 职责 |
|------|------|
| `backend/app/strategies/cta/trend_ma.py` | `TrendMaStrategy` |
| `backend/app/strategies/cta/registry.py` | 注册 |
| `backend/app/services/backtest_engine.py` | `STRATEGIES` 元数据 |
| `backend/app/schemas/backtest.py` | ADX/止损可选字段 |
| `backend/app/services/backtest_bars.py` | 可配置最低根数 |
| `backend/app/services/backtest_repo.py` | 放行策略 + setting 组装 |
| `backend/app/worker/tasks_backtest.py` | subprocess setting 透传 |
| `backend/tests/test_backtest_cta_trend_ma.py` | registry + vnpy 冒烟 |
| `docs/product-roadmap.md` / smoke | 收口 |

---

### Task 1: TrendMaStrategy + registry

**Files:**
- Create: `backend/app/strategies/cta/trend_ma.py`
- Modify: `backend/app/strategies/cta/registry.py`
- Modify: `backend/tests/test_backtest_cta_double_ma.py` 或 Create: `backend/tests/test_backtest_cta_trend_ma.py`

**Interfaces:**
- Produces: `class TrendMaStrategy(AShareCtaTemplate)` 含 spec 买卖条件
- Produces: `get_strategy_class("trend_ma") -> TrendMaStrategy`

- [ ] **Step 1: 写失败测试**

```python
import pytest
pytest.importorskip("vnpy_ctastrategy")

@pytest.mark.vnpy
def test_registry_trend_ma():
    from app.strategies.cta.registry import get_strategy_class
    assert get_strategy_class("trend_ma").__name__ == "TrendMaStrategy"
```

- [ ] **Step 2: 实现 `trend_ma.py`（对照桌面 `zak/strategies/trend_ma_strategy.py` 只读）**

要点：
- `on_init`：`ArrayManager(size=max(slow, adx_period*2)+10)`
- `on_bar`：预热 `am.count < max(slow, adx_period*2)+2` 则 return
- `adx_value = float(am.adx(self.adx_period))`
- 持仓：更新 highest；死叉 / close<slow / 追踪止损 → `sell_stock`
- 空仓：金叉 + adx≥阈值 + close>slow + slow 向上 → `buy_stock` 后设 `entry_price`/`highest_since_entry`
- `buy_stock` 无返回值：调用后即写入 entry（qty 有效时）

- [ ] **Step 3: registry 注册 → 测试绿 → Commit**

```bash
git commit -m "$(cat <<'EOF'
feat(backtest): 增加 trend_ma CTA 策略类

日 K 趋势双均线叠加 ADX 过滤与追踪止损。
EOF
)"
```

---

### Task 2: Schema + STRATEGIES + 日 K 最低根数

**Files:**
- Modify: `backend/app/schemas/backtest.py`
- Modify: `backend/app/services/backtest_engine.py`
- Modify: `backend/app/services/backtest_bars.py`
- Test: `backend/tests/test_backtest_schemas.py`（断言默认 ADX 字段）

**Interfaces:**
- `BacktestRunRequest` / `BatchBacktestRequest` / `OptimizeBacktestRequest` 增加：
  - `adx_period: int = 14`（ge=2）
  - `adx_threshold: float = 25.0`（ge=0）
  - `trailing_stop_pct: float = 0.12`（gt=0, le=1）
- `load_daily_bars(..., min_bars: int = 30)`
- `STRATEGIES` 增加：
  ```python
  {
    "id": "trend_ma",
    "name": "趋势双均线（ADX）",
    "interval": "d",
    "description": "金叉+ADX过滤买入；死叉/破慢线/追踪止损卖出；整手 T+1",
    "implemented": True,
    "engine": "vnpy",
  }
  ```

- [ ] **Step 1: schema 默认值测试 → 实现字段**
- [ ] **Step 2: `load_daily_bars` 接受 `min_bars`，文案含「需要至少 {min_bars} 根」**
- [ ] **Step 3: Commit**

```bash
git commit -m "$(cat <<'EOF'
feat(backtest): trend_ma 请求字段与策略元数据

ADX/止损参数入 schema，并支持可配置最低日 K 根数。
EOF
)"
```

---

### Task 3: Repo / Worker 放行与 setting 组装

**Files:**
- Modify: `backend/app/services/backtest_repo.py`
- Modify: `backend/app/worker/tasks_backtest.py`
- Test: `backend/tests/test_backtest_cta_trend_ma.py`（vnpy 合成 K 冒烟 + 未知策略）

**Interfaces:**
- Produces:
  ```python
  def build_strategy_setting(req: BacktestRunRequest) -> dict:
      base = {
          "fast_window": req.fast_window,
          "slow_window": req.slow_window,
          "trade_volume": 100,
      }
      if req.strategy == "trend_ma":
          base.update({
              "adx_period": req.adx_period,
              "adx_threshold": req.adx_threshold,
              "trailing_stop_pct": req.trailing_stop_pct,
          })
      return base

  def min_bars_for_request(req: BacktestRunRequest) -> int:
      if req.strategy == "trend_ma":
          return max(30, req.slow_window + req.adx_period * 2 + 5)
      return 30
  ```
- `execute_single`：`get_strategy_class(req.strategy)` 失败 → 501；`load_daily_bars(..., min_bars=...)`；setting 用 `build_strategy_setting`
- subprocess payload 的 `setting` 用同一函数（避免双份逻辑）：可把 `build_strategy_setting` 放 repo 或小模块 `backtest_settings.py`

- [ ] **Step 1: 未知策略测试（KeyError→501）**
- [ ] **Step 2: vnpy 冒烟（≥100 根合成 bar，strategy_id=trend_ma）**
- [ ] **Step 3: 改 repo + worker → 测过 → Commit**

```bash
git commit -m "$(cat <<'EOF'
feat(backtest): 回测管线放行 trend_ma

按策略组装 CTA setting，并提高趋势策略日 K 门槛。
EOF
)"
```

---

### Task 4: 路线图 / smoke / spec 状态 + 验收

**Files:**
- Modify: `docs/product-roadmap.md` — 基线文案「回测薄」可改为含 vnpy/多策略；新增完成项 #49
- Modify: `docs/smoke-checklist.md` — 一条：策略下拉含趋势双均线（ADX）
- Modify: spec 状态 → `已批准`

- [ ] **Step 1: UI 确认** `BacktestView` 已 `v-for="s in strategies"`，无需改前端（若默认仍 `double_ma` 可保留）
- [ ] **Step 2: `./scripts/check.sh`**
- [ ] **Step 3: Commit**

```bash
git commit -m "$(cat <<'EOF'
docs(backtest): 记录 trend_ma 第二策略完成

更新路线图与 smoke 验收项。
EOF
)"
```

---

## Self-review

1. Spec 买卖条件、默认参数、min_bars、registry、repo 放行均有 Task。  
2. 无 TBD；ADX 优先 `am.adx`。  
3. `build_strategy_setting` 单点复用，避免 repo/worker 分叉。

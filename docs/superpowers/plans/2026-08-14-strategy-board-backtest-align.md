# 看盘 ↔ 回测信号对齐 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** 看盘双模式（heuristic_v2 / double_ma）预热双轨 cache，UI 可切换，并支持同参预填跳转回测。

**Architecture:** 共享 `sma`/`cross_kind`；新增当日交叉 `compute_double_ma_signal`；warm 对每窗口额外写 `double_ma:{fast}:{slow}`；`strategy-board?signal_mode=` 解析 key；Watchlist + BacktestView query 联动。

**Tech Stack:** FastAPI、SQLAlchemy、Vue 3、pytest

**Spec:** `docs/superpowers/specs/2026-08-14-strategy-board-backtest-align-design.md`

## Global Constraints

- 只改 zak2；不改 `DoubleMaStrategy` / `TrendMaStrategy` 买卖逻辑
- 不做 `trend_ma` 看盘；不做请求路径现算
- 默认 `signal_mode=heuristic_v2`；`double_ma` 默认窗口 5:20
- Redis 桥不伪造 `double_ma:*`
- 一键回测只预填，不自动 `startRun`
- commit 简体中文；`./scripts/check.sh` 绿

## File map

| 路径 | 职责 |
|------|------|
| `backend/app/services/strategy_signal_ma.py` | `compute_double_ma_signal`；heuristic 写 `signal_mode` |
| `backend/app/services/ops_warm_watchlist_strategy.py` | 双轨 upsert |
| `backend/app/services/strategy_board.py` | mode→key；Out.`signal_mode`；note |
| `backend/app/schemas/watchlist.py` | `signal_mode` 字段 |
| `backend/app/api/v1/watchlist.py` | query `signal_mode` |
| `backend/app/services/ops_catalog.py` | warm 文案 |
| `frontend/src/api/watchlist.ts` | API 参数 |
| `frontend/src/views/WatchlistView.vue` | 模式切换 + 同参回测 |
| `frontend/src/views/BacktestView.vue` | query 预填 |
| docs | #53 + smoke + spec 状态 |

---

### Task 1: `compute_double_ma_signal` + heuristic 标注 mode

**Files:**
- Modify: `backend/app/services/strategy_signal_ma.py`
- Test: 扩展 `backend/tests/test_strategy_signal_ma.py`

**Interfaces:**
- `compute_double_ma_signal(closes, *, volumes=None, fast, slow, vt_symbol, as_of) -> dict | None`
- 金叉当日 buy / 死叉 sell / 否则 hold；无 pending；`signal_mode="double_ma"`；reason 含「双均线当日交叉（对齐回测 double_ma）」；强度档同 `strength_tier_for`
- 最低 `len(closes) >= slow + 1`（昨今有效均线）
- `compute_ma_signal` 返回值增加 `"signal_mode": "heuristic_v2"`

- [x] **Step 1: 写失败测试（合成收盘序列）**

```python
def test_double_ma_same_day_cross_is_buy():
    # 构造慢线平稳、快线向上穿越的 closes
    from app.services.strategy_signal_ma import compute_double_ma_signal, compute_ma_signal
    closes = [...]  # 长度足够 slow+1；末两根形成金叉
    d = compute_double_ma_signal(closes, fast=5, slow=20, vt_symbol="600519.SSE", as_of="2024-06-01")
    h = compute_ma_signal(closes, fast=5, slow=20, vt_symbol="600519.SSE", as_of="2024-06-01")
    assert d["signal"] == "buy"
    assert d["signal_mode"] == "double_ma"
    assert h["signal"] == "hold"  # 确认日前
    assert h["signal_mode"] == "heuristic_v2"
```

（closes 可用现有测试里的序列或手写：前段横盘，末段上穿。）

- [x] **Step 2: 实现 → 绿 → Commit**

```bash
git commit -m "$(cat <<'EOF'
feat(strategy): 增加 double_ma 当日交叉看盘信号

与启发式确认模式共用均线交叉定义。
EOF
)"
```

---

### Task 2: warm 双轨写入

**Files:**
- Modify: `backend/app/services/ops_warm_watchlist_strategy.py`
- Modify: `backend/app/services/ops_catalog.py`
- Test: 扩展 `backend/tests/test_ops_warm_watchlist_strategy.py`

**Interfaces:**
- `_compute_pool`：对每个可解析 ck，在 heuristic upsert 后，用同一 `closes` 调 `compute_double_ma_signal`，`config_key=f"double_ma:{fast}:{slow}"` upsert；payload 已含 mode
- 去重：同一 `(fast,slow)` 的 double_ma key 只算一次（用 `seen_dm: set[tuple[int,int]]`）
- 结束后若 `(5,20)` 未在 seen → 对池再算一轮 `double_ma:5:20`（或并入 keys 列表预置）
- `message` 含 `double_ma` / 双轨字样
- catalog：`双均线启发式 v2 + double_ma 双轨 → watchlist_signal_cache`

- [x] **Step 1: mock `_load_daily_closes` + 断言 `_upsert_signal` 被以 `double_ma:` 前缀调用**

- [x] **Step 2: 实现 → 绿 → Commit**

```bash
git commit -m "$(cat <<'EOF'
feat(ops): 策略预热双轨写入 double_ma cache

切换看盘模式时无需重算即可读当日交叉信号。
EOF
)"
```

---

### Task 3: board resolve + API

**Files:**
- Modify: `backend/app/services/strategy_board.py`
- Modify: `backend/app/schemas/watchlist.py`
- Modify: `backend/app/api/v1/watchlist.py`
- Test: 扩展 `backend/tests/test_strategy_board.py`

**Interfaces:**
- `SIGNAL_MODE_HEURISTIC = "heuristic_v2"`；`SIGNAL_MODE_DOUBLE_MA = "double_ma"`
- `def double_ma_config_key(fast: int, slow: int) -> str: return f"double_ma:{fast}:{slow}"`
- `def resolve_board_config_key(db, user_id, *, signal_mode: str = "heuristic_v2", override: str | None = None) -> str`
  - heuristic：现 `resolve_config_key`
  - double_ma：从用户偏好 parse `(fast,slow)`，失败则 5,20 → `double_ma_config_key`
  - override 非空：若以 `double_ma:` 开头或 heuristic 合法则直接用
- `load_strategy_board(..., signal_mode: str = "heuristic_v2", config_key: str | None = None)`  
  - `ck = resolve_board_config_key(...)`  
  - 返回 dict 增 `signal_mode`  
  - `note`：heuristic → 确认 N=2 文案；double_ma → 「当日交叉，规则对齐回测 double_ma（非 vnpy 进程）」
- Schema：`StrategyBoardOut.signal_mode: str = "heuristic_v2"`
- API：`signal_mode: str = Query(default="heuristic_v2")` 传入 `load_strategy_board`

- [x] **Step 1: 单测 resolve 默认 5:20；用户偏好 5:10 → `double_ma:5:10`**

- [x] **Step 2: 实现 → 绿 → Commit**

```bash
git commit -m "$(cat <<'EOF'
feat(strategy): strategy-board 支持 signal_mode

按模式解析 config_key 并返回说明文案。
EOF
)"
```

---

### Task 4: Watchlist UI + Backtest 预填

**Files:**
- Modify: `frontend/src/api/watchlist.ts`
- Modify: `frontend/src/views/WatchlistView.vue`
- Modify: `frontend/src/views/BacktestView.vue`
- Test: 后端已覆盖；前端 `npm run build`

**Interfaces:**
- `strategyBoard({ signal_mode?: string, config_key?: string })`
- Watchlist：`signalMode` ref；两按钮/select；`loadBoard` 带 mode；展示 `board.signal_mode` / note
- 「同参回测」：取当前信号表第一行或选中行 `vt_symbol`，以及从 `board.config_key` parse fast/slow（`double_ma:5:20` → 5,20；heuristic key 取末两段），`router.push({ path:'/backtest', query:{ strategy:'double_ma', vt_symbol, fast_window, slow_window }})`
- BacktestView：`onMounted` 读 `useRoute().query`：若有 `vt_symbol`/`strategy`/`fast_window`/`slow_window` 则写入对应 ref；**不**调用 `startRun`

- [x] **Step 1: 实现 UI + query 预填**

- [x] **Step 2: `npm run build` → Commit**

```bash
git commit -m "$(cat <<'EOF'
feat(ui): 看盘双模式切换与同参回测预填

对齐规则说明，回测页只预填不开跑。
EOF
)"
```

---

### Task 5: 文档收口

**Files:**
- `docs/product-roadmap.md` #53
- `docs/smoke-checklist.md`
- spec 状态 → 已批准（已实现）

- [x] **Step 1: 更新文档**

- [x] **Step 2: `./scripts/check.sh` → Commit**

```bash
git commit -m "$(cat <<'EOF'
docs(strategy): 记录看盘回测信号对齐完成

更新路线图与 smoke。
EOF
)"
```

---

## Self-review

1. Spec：双轨 warm、mode API、UI、预填回测、共享交叉、非目标 CTA → Task 1–5。  
2. 无 TBD。  
3. key `double_ma:{fast}:{slow}` 与 `signal_mode` 命名一致。

## Execution

建议 worktree：`feat/strategy-board-backtest-align`。

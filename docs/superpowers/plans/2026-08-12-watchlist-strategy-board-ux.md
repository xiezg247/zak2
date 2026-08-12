# 自选策略看盘 UX 闭环 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 策略看盘 `note`/空态/tip 去桌面依赖，对齐 zak2 独立演进语义。

**Architecture:** 仅改 `strategy_board.load_strategy_board` 三条 note 字符串 + `WatchlistView` 对应空态/tip；扩展既有 pytest；不接引擎、不写 cache。

**Tech Stack:** Python pytest mock、Vue 3

**Spec:** `docs/superpowers/specs/2026-08-12-watchlist-strategy-board-ux-design.md`

## Global Constraints

- 只改 zak2；不改 zak / vnpy-*
- 不实现策略引擎；不把 `warm_watchlist_strategy_cache` 做实
- 不改风控卡片「与桌面同表」文案（本刀仅信号/持仓区）
- 所有新 `note`/空态文案 **不得** 含「桌面」
- commit message 简体中文：`<type>(<scope>): <简述>`

## File map

| 路径 | 职责 |
|------|------|
| `backend/app/services/strategy_board.py` | 三条 `note` 文案 |
| `backend/tests/test_strategy_board.py` | note 分支断言 |
| `frontend/src/views/WatchlistView.vue` | 信号空行、名单 tip、持仓 tip |
| `docs/smoke-checklist.md` / `product-roadmap.md` | 文档 |

---

### Task 1: 后端 note + 单测

**Files:**
- Modify: `backend/app/services/strategy_board.py`
- Modify: `backend/tests/test_strategy_board.py`

**Interfaces:**
- Consumes: 现有 `load_strategy_board` 分支条件（不变）
- Produces: 新 note 字符串；测试断言无「桌面」

- [ ] **Step 1: 写/改失败测试**

在 `test_strategy_board.py` 更新空看板断言，并新增两条分支（复用 empty 测试的 mock 骨架）：

```python
def test_load_strategy_board_empty() -> None:
    # ... existing mocks ...
    out = strategy_board.load_strategy_board(db, "u1")
    assert out["note"]
    assert "桌面" not in out["note"]
    assert "尚未接入策略引擎" in out["note"]


def test_load_strategy_board_note_panel_no_signals() -> None:
    from app.services import strategy_board

    db = MagicMock()

    def _execute(stmt, params=None):  # noqa: ANN001
        _ = params
        result = MagicMock()
        sql = str(stmt)
        if "user_preferences" in sql:
            result.scalar.return_value = None
        else:
            result.mappings.return_value.all.return_value = []
            result.mappings.return_value.first.return_value = None
        return result

    db.execute.side_effect = _execute
    with (
        patch.object(strategy_board.repo, "list_items", return_value=[]),
        patch.object(
            strategy_board.signal_panel_repo,
            "load_symbols",
            return_value=["600519.SSE"],
        ),
        patch.object(strategy_board, "_scan_signal_redis", return_value=[]),
        patch.object(strategy_board, "get_quote_store") as gs,
        patch(
            "app.services.strategy_board.load_trading_risk_prefs",
            return_value={
                "total_capital": None,
                "stop_loss_pct": 0.05,
                "caution_float_pct": -5.0,
                "realized_pnl_today": None,
            },
        ),
        patch(
            "app.services.strategy_board.load_active_plan_snapshot",
            return_value=None,
        ),
        patch(
            "app.services.strategy_board.latest_open_yyyymmdd",
            return_value="20260805",
        ),
    ):
        gs.return_value.available.return_value = False
        out = strategy_board.load_strategy_board(db, "u1")
    assert out["panel_symbols"] == ["600519.SSE"]
    assert out["signals"] == []
    assert "桌面" not in out["note"]
    assert "信号名单 1 只" in out["note"]


def test_load_strategy_board_note_positions_no_signals() -> None:
    from app.services import strategy_board

    db = MagicMock()

    def _execute(stmt, params=None):  # noqa: ANN001
        _ = params
        result = MagicMock()
        sql = str(stmt)
        if "user_preferences" in sql:
            result.scalar.return_value = None
        elif "watchlist_positions" in sql or "FROM app.watchlist_positions" in sql:
            result.mappings.return_value.all.return_value = [
                {
                    "symbol": "600519",
                    "exchange": "SSE",
                    "cost_price": 100.0,
                    "volume": 100,
                    "buy_date": "2026-01-01",
                    "notes": "",
                    "source": "manual",
                    "plan_pct": None,
                    "sort_order": 0,
                }
            ]
            result.mappings.return_value.first.return_value = None
        else:
            result.mappings.return_value.all.return_value = []
            result.mappings.return_value.first.return_value = None
        return result

    db.execute.side_effect = _execute
    with (
        patch.object(strategy_board.repo, "list_items", return_value=[]),
        patch.object(strategy_board.signal_panel_repo, "load_symbols", return_value=[]),
        patch.object(strategy_board, "_scan_signal_redis", return_value=[]),
        patch.object(strategy_board, "get_quote_store") as gs,
        patch(
            "app.services.strategy_board.load_trading_risk_prefs",
            return_value={
                "total_capital": None,
                "stop_loss_pct": 0.05,
                "caution_float_pct": -5.0,
                "realized_pnl_today": None,
            },
        ),
        patch(
            "app.services.strategy_board.load_active_plan_snapshot",
            return_value=None,
        ),
        patch(
            "app.services.strategy_board.latest_open_yyyymmdd",
            return_value="20260805",
        ),
    ):
        gs.return_value.available.return_value = False
        out = strategy_board.load_strategy_board(db, "u1")
    assert out["positions"]
    assert out["signals"] == []
    assert "桌面" not in out["note"]
    assert "持仓来自记账表" in out["note"]
```

（若 positions SQL 匹配不准：对照 `load_strategy_board` 内实际 `text(...)` 字符串调整 `elif` 分支，或 patch 返回 positions 的内部 helper——以现有 `test_load_strategy_board_risk_summary_with_off_plan` 为模板。）

- [ ] **Step 2: 跑测确认 RED**

```bash
cd backend && uv run pytest tests/test_strategy_board.py -k "note or empty" -v
```

Expected: 因旧文案含「桌面」或缺少新短语而 FAIL

- [ ] **Step 3: 改 note 文案**

`strategy_board.py` 末尾替换为：

```python
    note = ""
    if panel_symbols and not signals:
        note = (
            f"信号名单 {len(panel_symbols)} 只，暂无策略 cache"
            "（可编辑名单，或确认 Redis/PG 已有信号缓存）。"
        )
    elif not signals and not positions:
        note = (
            "暂无策略缓存。zak2 尚未接入策略引擎预热；"
            "可先维护信号名单与持仓记账，或确认 Redis/PG cache 已写入。"
        )
    elif not signals:
        note = "持仓来自记账表；信号 cache 为空（可编辑名单，或确认 cache 已写入）。"
```

- [ ] **Step 4: 跑测 GREEN**

```bash
cd backend && uv run pytest tests/test_strategy_board.py -q
```

Expected: 全绿

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/strategy_board.py backend/tests/test_strategy_board.py
git commit -m "$(cat <<'EOF'
fix(watchlist): 策略看盘 note 去桌面依赖

空态改为 zak2 语义；单测覆盖三条 note 分支。
EOF
)"
```

---

### Task 2: 前端 tip + 文档 + check.sh

**Files:**
- Modify: `frontend/src/views/WatchlistView.vue`
- Modify: `docs/smoke-checklist.md`
- Modify: `docs/product-roadmap.md`

- [ ] **Step 1: 改三处文案**

```html
<!-- 名单 tip -->
<p v-else class="muted tip">名单为空时回退「自选 ∩ 策略 cache」；上限 {{ panelMax }} 只（存 PG）。</p>

<!-- 信号空行 -->
<td colspan="7" class="empty">无信号（可先编辑名单，或确认策略 cache 已写入）</td>

<!-- 持仓 tip -->
<p class="muted tip">须先加入自选；数量 100 股整手；写入持仓记账表。</p>
```

确认风控区「与桌面同表 trading/risk」**未改**。

- [ ] **Step 2: smoke + roadmap**

smoke 自选节增加或改写：

```markdown
- [ ] `/watchlist` 策略看盘空态 / note 可读，文案不引导「桌面刷新」
```

roadmap 近期待办增加：

```markdown
11. ~~策略看盘 UX 闭环~~（已完成 → [spec](./superpowers/specs/2026-08-12-watchlist-strategy-board-ux-design.md)）
```

- [ ] **Step 3: check.sh**

```bash
./scripts/check.sh
```

Expected: 全绿

- [ ] **Step 4: Commit**

```bash
git add frontend/src/views/WatchlistView.vue docs/smoke-checklist.md docs/product-roadmap.md
git commit -m "$(cat <<'EOF'
fix(watchlist): 策略看盘空态文案对齐 zak2

同步 tip/空行；更新 smoke 与路线图。
EOF
)"
```

---

## Spec coverage（自审）

| Spec | Task |
|------|------|
| 三条 note | 1 |
| 前端三处文案 | 2 |
| 测试无「桌面」 | 1 |
| smoke / roadmap | 2 |

无 TBD。

# AI 只读持仓/信号/风控 + positions Skill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Agent 可只读查询持仓、信号名单、风控 prefs+risk_summary，并经 `run_skill` 调用 `positions` Skill 聚合或分流。

**Architecture:** 在 `ai_read_tools.py` 增加三个 helper；`ai_tools.py` 注册只读 definitions/handlers（不入 WRITE）；新增 `app/skills/positions/` 薄 Skill，默认聚合、可按 `section` 分流。

**Tech Stack:** FastAPI Session、现有 `positions_repo` / `signal_panel_repo` / `trading_risk` / `strategy_board`、pytest mock

**Spec:** `docs/superpowers/specs/2026-08-11-ai-read-positions-signals-design.md`

## Global Constraints

- 只改 zak2；不改 zak / vnpy-*；不改 REST / 确认卡 / 写工具语义
- 三工具 **不在** `WRITE_TOOL_NAMES`
- `get_trading_risk` 返回 `{ prefs, risk_summary }`；允许先 `load_strategy_board` 再取 summary
- Skill id 精确为 `positions`
- commit message 简体中文：`<type>(<scope>): <简述>`

## File map

| 路径 | 职责 |
|------|------|
| `backend/app/services/ai_read_tools.py` | `get_positions` / `get_signal_panel` / `get_trading_risk` |
| `backend/app/services/ai_tools.py` | 薄 wrapper + TOOL_HANDLERS + TOOL_DEFINITIONS |
| `backend/app/skills/positions/SKILL.md` | Skill 说明 |
| `backend/app/skills/positions/skill.py` | run：聚合 / section 分流 |
| `backend/tests/test_ai_read_tools.py` | helper + execute_tool / run_skill 测 |
| `backend/tests/test_ai_tools.py` | definitions / WRITE 集合 |
| `backend/tests/test_skills_catalog.py` | catalog 含 positions |
| `docs/product-roadmap.md` / `docs/smoke-checklist.md` | 文档 |

---

### Task 1: `ai_read_tools` 三个只读 helper

**Files:**
- Modify: `backend/app/services/ai_read_tools.py`
- Modify: `backend/tests/test_ai_read_tools.py`

**Interfaces:**
- Produces:
  - `get_positions(db, user_id, args) -> {count, items}`
  - `get_signal_panel(db, user_id, args) -> {symbols, count, max_symbols}`
  - `get_trading_risk(db, user_id, args) -> {prefs, risk_summary}`
- Consumes: `positions_repo.list_positions`、`signal_panel_repo.panel_payload`、`trading_risk.load_trading_risk_prefs`、`strategy_board.load_strategy_board`

- [ ] **Step 1: 写失败测试**

在 `backend/tests/test_ai_read_tools.py` 追加：

```python
def test_get_positions_limit_and_shape() -> None:
    rows = [
        {
            "symbol": "600519",
            "exchange": "SSE",
            "vt_symbol": "600519.SSE",
            "cost_price": 100.0,
            "volume": 100,
            "buy_date": "2026-08-01",
            "notes": "",
            "source": "manual",
            "plan_pct": None,
            "sort_order": 0,
            "created_at": "",
            "updated_at": "",
        },
        {
            "symbol": "000001",
            "exchange": "SZSE",
            "vt_symbol": "000001.SZSE",
            "cost_price": 10.0,
            "volume": 200,
            "buy_date": "2026-07-01",
            "notes": "",
            "source": "manual",
            "plan_pct": 0.1,
            "sort_order": 1,
            "created_at": "",
            "updated_at": "",
        },
    ]
    with patch.object(art, "positions_repo") as pref:
        pref.list_positions.return_value = rows
        with patch.object(art, "get_quote_store") as gq:
            store = MagicMock()
            store.get_quotes.return_value = []
            gq.return_value = store
            out = art.get_positions(MagicMock(), "u", {"limit": 1, "with_quotes": True})
    assert out["count"] == 1
    assert out["items"][0]["vt_symbol"] == "600519.SSE"
    pref.list_positions.assert_called_once()


def test_get_signal_panel_delegates() -> None:
    payload = {"symbols": ["600519.SSE"], "count": 1, "max_symbols": 10}
    with patch.object(art, "signal_panel_repo") as sp:
        sp.panel_payload.return_value = payload
        out = art.get_signal_panel(MagicMock(), "u", {})
    assert out == payload
    sp.panel_payload.assert_called_once()


def test_get_trading_risk_prefs_and_summary() -> None:
    prefs = {
        "total_capital": 100000.0,
        "stop_loss_pct": 0.05,
        "caution_float_pct": -5.0,
        "realized_pnl_today": None,
    }
    board = {
        "risk_summary": {
            "total_capital": 100000.0,
            "actual_position_pct": 0.2,
            "plan_max_pct": 0.5,
            "off_plan_count": 0,
            "off_plan_symbols": [],
            "active_plan_date": "2026-08-11",
            "plan_symbols": [
                {"vt_symbol": "600519.SSE", "status": "in_position", "name": "茅台", "extra": "drop_me"},
            ],
        }
    }
    with (
        patch.object(art, "trading_risk") as tr,
        patch.object(art, "strategy_board") as sb,
    ):
        tr.load_trading_risk_prefs.return_value = prefs
        sb.load_strategy_board.return_value = board
        out = art.get_trading_risk(MagicMock(), "u", {})
    assert out["prefs"]["total_capital"] == 100000.0
    assert out["risk_summary"]["actual_position_pct"] == 0.2
    assert out["risk_summary"]["plan_symbols"] == [
        {"vt_symbol": "600519.SSE", "status": "in_position"}
    ]
```

（实现后若 `positions_repo` / `signal_panel_repo` / `trading_risk` / `strategy_board` 以模块级 import 挂在 `ai_read_tools`，上述 `patch.object(art, ...)` 成立；若局部 import，改为 patch `app.services.positions_repo.list_positions` 等。）

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && uv run pytest tests/test_ai_read_tools.py::test_get_positions_limit_and_shape tests/test_ai_read_tools.py::test_get_signal_panel_delegates tests/test_ai_read_tools.py::test_get_trading_risk_prefs_and_summary -v`  
Expected: FAIL（属性/函数不存在）

- [ ] **Step 3: 实现 helper**

在 `ai_read_tools.py` 顶部 import 增加：

```python
from app.services import positions_repo, signal_panel_repo, strategy_board, trading_risk
```

（保留现有 `market, notes, radar, screener_repo, watchlist_repo`。）

追加：

```python
def get_positions(db: Session, user_id: str, args: dict[str, Any]) -> Any:
    limit = max(1, min(int(args.get("limit") or 20), 20))
    with_quotes = bool(args.get("with_quotes", True))
    items = list(positions_repo.list_positions(db, user_id)[:limit])
    if with_quotes and items:
        store = get_quote_store()
        try:
            from app.services.symbols import to_tf_symbol

            tf_map = {to_tf_symbol(r["symbol"], r["exchange"]): r for r in items}
            quotes = store.get_quotes(list(tf_map.keys()))
            for q in quotes:
                target = tf_map.get(q.symbol)
                if target is None:
                    continue
                target["last_price"] = q.last_price
                target["change_pct"] = q.change_pct
                if getattr(q, "name", None):
                    target["name"] = q.name
        except Exception:  # noqa: BLE001
            pass
    return {"count": len(items), "items": items}


def get_signal_panel(db: Session, user_id: str, args: dict[str, Any]) -> Any:
    _ = args
    return signal_panel_repo.panel_payload(db, user_id)


def get_trading_risk(db: Session, user_id: str, args: dict[str, Any]) -> Any:
    config_key = args.get("config_key")
    prefs = trading_risk.load_trading_risk_prefs(db, user_id)
    board = strategy_board.load_strategy_board(
        db, user_id, config_key=str(config_key) if config_key else None
    )
    raw_summary = dict(board.get("risk_summary") or {})
    plan_symbols = []
    for row in list(raw_summary.get("plan_symbols") or []):
        if isinstance(row, dict):
            plan_symbols.append(
                {
                    "vt_symbol": row.get("vt_symbol"),
                    "status": row.get("status"),
                }
            )
        else:
            plan_symbols.append(row)
    raw_summary["plan_symbols"] = plan_symbols
    return {"prefs": prefs, "risk_summary": raw_summary}
```

注意：`load_strategy_board` 的 `config_key` 签名以源码为准（可能 `config_key: str | None = None`）；若关键字不同，按实际参数名对接。

- [ ] **Step 4: 跑测试确认通过**

```bash
cd backend && uv run pytest tests/test_ai_read_tools.py -q
```

Expected: PASS（含原有用例）

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/ai_read_tools.py backend/tests/test_ai_read_tools.py
git commit -m "$(cat <<'EOF'
feat(ai): 增加持仓/信号/风控只读 helper

供 Agent 工具与 positions Skill 复用，risk_summary 截断 plan_symbols。
EOF
)"
```

---

### Task 2: 注册 `ai_tools` 只读定义与 dispatch

**Files:**
- Modify: `backend/app/services/ai_tools.py`
- Modify: `backend/tests/test_ai_tools.py`
- Modify: `backend/tests/test_ai_read_tools.py`（追加 execute_tool 委托测）

**Interfaces:**
- Produces: `TOOL_HANDLERS` / `TOOL_DEFINITIONS` 含 `get_positions`、`get_signal_panel`、`get_trading_risk`
- Consumes: Task 1 helpers

- [ ] **Step 1: 写失败测试**

`test_ai_tools.py`（或现有集合测文件）追加：

```python
from app.services.ai_tools import WRITE_TOOL_NAMES, get_tool_definitions, TOOL_HANDLERS


def test_read_position_tools_registered_not_write() -> None:
    names = {d["function"]["name"] for d in get_tool_definitions() if d.get("type") == "function"}
    for n in ("get_positions", "get_signal_panel", "get_trading_risk"):
        assert n in names
        assert n in TOOL_HANDLERS
        assert n not in WRITE_TOOL_NAMES
```

`test_ai_read_tools.py` 追加：

```python
def test_ai_tools_delegates_get_positions() -> None:
    with patch("app.services.ai_read_tools.get_positions", return_value={"count": 0, "items": []}) as m:
        raw = execute_tool(MagicMock(), "u", "get_positions", {"limit": 5})
    assert "count" in raw
    m.assert_called_once()
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && uv run pytest tests/test_ai_tools.py::test_read_position_tools_registered_not_write tests/test_ai_read_tools.py::test_ai_tools_delegates_get_positions -v`  
Expected: FAIL

- [ ] **Step 3: 接线**

在 `ai_tools.py` 增加 wrapper（与 `_get_watchlist` 同风格）：

```python
def _get_positions(db: Session, user_id: str, args: dict[str, Any]) -> Any:
    from app.services import ai_read_tools

    return ai_read_tools.get_positions(db, user_id, args)


def _get_signal_panel(db: Session, user_id: str, args: dict[str, Any]) -> Any:
    from app.services import ai_read_tools

    return ai_read_tools.get_signal_panel(db, user_id, args)


def _get_trading_risk(db: Session, user_id: str, args: dict[str, Any]) -> Any:
    from app.services import ai_read_tools

    return ai_read_tools.get_trading_risk(db, user_id, args)
```

注册到 `TOOL_HANDLERS`：

```python
"get_positions": _get_positions,
"get_signal_panel": _get_signal_panel,
"get_trading_risk": _get_trading_risk,
```

在 `TOOL_DEFINITIONS` 中于合适位置（建议紧接 `get_watchlist` 后）追加三条：

```python
{
    "type": "function",
    "function": {
        "name": "get_positions",
        "description": "获取当前用户记账持仓列表，可选附带最新行情",
        "parameters": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "最多返回条数，默认 20，上限 20"},
                "with_quotes": {"type": "boolean", "description": "是否附带行情，默认 true"},
            },
        },
    },
},
{
    "type": "function",
    "function": {
        "name": "get_signal_panel",
        "description": "获取当前用户自选信号名单（vt_symbol 列表）",
        "parameters": {"type": "object", "properties": {}},
    },
},
{
    "type": "function",
    "function": {
        "name": "get_trading_risk",
        "description": "获取交易风控偏好与仓位/计划外摘要（risk_summary）",
        "parameters": {
            "type": "object",
            "properties": {
                "config_key": {
                    "type": "string",
                    "description": "可选策略 config_key，缺省与策略看盘一致",
                },
            },
        },
    },
},
```

- [ ] **Step 4: 跑测试**

```bash
cd backend && uv run pytest tests/test_ai_tools.py tests/test_ai_read_tools.py tests/test_ai_write_positions.py -q
```

Expected: PASS（写工具回归仍绿）

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/ai_tools.py backend/tests/test_ai_tools.py backend/tests/test_ai_read_tools.py
git commit -m "$(cat <<'EOF'
feat(ai): 注册持仓/信号/风控只读 Agent 工具

不入 WRITE 集合，立即执行返回。
EOF
)"
```

---

### Task 3: Skill `positions` + catalog + 文档

**Files:**
- Create: `backend/app/skills/positions/SKILL.md`
- Create: `backend/app/skills/positions/skill.py`
- Modify: `backend/tests/test_skills_catalog.py`
- Modify: `backend/tests/test_ai_read_tools.py`
- Modify: `docs/product-roadmap.md`
- Modify: `docs/smoke-checklist.md`

**Interfaces:**
- Produces: `run(ctx, args)`；catalog id=`positions`
- Consumes: Task 1 helpers

- [ ] **Step 1: 写失败测试**

改 `test_skills_catalog.py`：

```python
def test_list_includes_positions() -> None:
    ids = {s["id"] for s in list_skills()}
    assert ids == {
        "watchlist",
        "market-emotion",
        "screener",
        "radar",
        "notes",
        "positions",
    }
```

（删除或替换旧的 `test_list_has_five`。）

`test_ai_read_tools.py`：

```python
def test_run_skill_positions_all() -> None:
    assert "get_positions" not in WRITE_TOOL_NAMES
    with (
        patch("app.services.ai_read_tools.get_positions", return_value={"count": 0, "items": []}) as gp,
        patch(
            "app.services.ai_read_tools.get_signal_panel",
            return_value={"symbols": [], "count": 0, "max_symbols": 10},
        ) as gs,
        patch(
            "app.services.ai_read_tools.get_trading_risk",
            return_value={"prefs": {}, "risk_summary": {}},
        ) as gr,
    ):
        out = execute_tool(MagicMock(), "u", "run_skill", {"skill_id": "positions"})
    assert "positions" in out and "signal_panel" in out and "trading_risk" in out
    gp.assert_called_once()
    gs.assert_called_once()
    gr.assert_called_once()


def test_run_skill_positions_section_signals() -> None:
    with patch(
        "app.services.ai_read_tools.get_signal_panel",
        return_value={"symbols": ["600519.SSE"], "count": 1, "max_symbols": 10},
    ) as gs:
        out = execute_tool(
            MagicMock(), "u", "run_skill", {"skill_id": "positions", "section": "signals"}
        )
    assert "600519" in out or "symbols" in out
    gs.assert_called_once()
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && uv run pytest tests/test_skills_catalog.py::test_list_includes_positions tests/test_ai_read_tools.py::test_run_skill_positions_all -v`  
Expected: FAIL（无 positions 目录 / catalog 集合不匹配）

- [ ] **Step 3: 实现 Skill**

`backend/app/skills/positions/SKILL.md`：

```markdown
---
name: positions
description: 持仓、信号名单与风控只读总览；写操作须用户确认
---

# 持仓与信号

触发：持仓、仓位、信号名单、风控、计划外。

| 工具 | 用途 |
|------|------|
| get_positions | 列出记账持仓 |
| get_signal_panel | 信号名单 |
| get_trading_risk | 风控偏好 + risk_summary |
| upsert_position / delete_position | 写持仓（须确认卡） |
| add_signal_panel / remove_signal_panel | 写信号名单（须确认卡） |
| run_skill | skill_id=positions；可 section=all\|positions\|signals\|risk |
```

`backend/app/skills/positions/skill.py`：

```python
from __future__ import annotations

from typing import Any

from app.services import ai_read_tools


def run(ctx: Any, args: dict[str, Any]) -> Any:
    args = args or {}
    section = str(args.get("section") or "all").strip().lower()
    if section in ("", "all"):
        return {
            "positions": ai_read_tools.get_positions(ctx.db, ctx.user_id, args),
            "signal_panel": ai_read_tools.get_signal_panel(ctx.db, ctx.user_id, args),
            "trading_risk": ai_read_tools.get_trading_risk(ctx.db, ctx.user_id, args),
        }
    if section in ("positions", "position"):
        return ai_read_tools.get_positions(ctx.db, ctx.user_id, args)
    if section in ("signals", "signal", "signal_panel"):
        return ai_read_tools.get_signal_panel(ctx.db, ctx.user_id, args)
    if section in ("risk", "trading_risk"):
        return ai_read_tools.get_trading_risk(ctx.db, ctx.user_id, args)
    return {"error": f"未知 section：{section}，可用 all|positions|signals|risk"}
```

文档：

- `product-roadmap.md`：将「候选：AI 只读持仓/信号工具」改为已完成并链本 spec  
- `smoke-checklist.md` Agent 行：补 `get_positions` / `get_signal_panel` / `get_trading_risk`；`run_skill` 含 **positions**

- [ ] **Step 4: 跑测试与 check**

```bash
cd backend && uv run pytest tests/test_ai_read_tools.py tests/test_skills_catalog.py tests/test_ai_tools.py tests/test_ai_tools_skills.py tests/test_ai_write_positions.py -q
./scripts/check.sh
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/skills/positions backend/tests/test_skills_catalog.py \
  backend/tests/test_ai_read_tools.py docs/product-roadmap.md docs/smoke-checklist.md
git commit -m "$(cat <<'EOF'
feat(ai): 增加 positions Skill 并更新路线图

run_skill 可聚合或按 section 分流持仓/信号/风控只读。
EOF
)"
```

---

## Spec coverage

| Spec | Task |
|------|------|
| `get_positions` / quotes / limit | 1–2 |
| `get_signal_panel` | 1–2 |
| `get_trading_risk` prefs + risk_summary 截断 | 1–2 |
| 不入 WRITE | 2 |
| Skill positions + section | 3 |
| roadmap / smoke | 3 |
| 不改 REST / 写工具 / 确认卡 | 遵守 |

## 执行交接

Plan 已保存到 `docs/superpowers/plans/2026-08-11-ai-read-positions-signals.md`。

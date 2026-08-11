# AI 写工具：持仓 + 信号名单 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development（推荐）或 executing-plans。步骤用 `- [ ]` 跟踪。

**Goal:** Agent 经确认卡可提议录入/更新/删除持仓与加入/移出信号名单；落库复用现有 repo。

**Architecture:** 在 `ai_tools.py` 扩展 4 个 `WRITE_TOOL_NAMES` handler + OpenAI definitions + summarize；确认卡 / proposal / AiView 不改。`upsert_position` 按是否已有持仓分支 `add_position` / `update_position`。

**Tech Stack:** FastAPI、现有 `positions_repo` / `signal_panel_repo`、pytest mock。

**Spec:** `docs/superpowers/specs/2026-08-10-ai-write-positions-signals-design.md`

## Global Constraints

- 只改 zak2；不改 zak；不 import vnpy_*
- 不改确认卡 UI / proposal 存储；不自动加自选
- Commit 仅用户明确要求时（默认跳过）
- 缺自选时 upsert 失败（文案含「须先加入自选」）
- `remove_signal_panel` 不在名单 → error（与 Web 一致）

**Clarifications:**

- 工具名精确：`upsert_position`、`delete_position`、`add_signal_panel`、`remove_signal_panel`
- 摘要统一：`录入/更新持仓：{vt} 成本{cost} 数量{vol}`、`删除持仓：…`、`加入信号名单：…`、`移出信号名单：…`
- HTTPException → handler 内 `{error: detail}`（与 `_add_watchlist` 同）

---

## File map

| 文件 | 职责 |
|------|------|
| `backend/app/services/ai_tools.py` | 4 写工具 + definitions + summarize + WRITE 集合 |
| `backend/tests/test_ai_write_positions.py` | **新建** mock 行为测 |
| `backend/tests/test_ai_tools.py` | 更新 TOOL_DEFINITIONS / handlers 集合 |
| `backend/tests/test_ai_proposals.py` | 更新 WRITE 集合与 summarize 断言 |
| `docs/gap-vs-desktop.md` / `docs/smoke-checklist.md` | 文档 |

---

### Task 1: 四个写工具 + 单测 + 集合断言

**Files:**
- Modify: `backend/app/services/ai_tools.py`
- Create: `backend/tests/test_ai_write_positions.py`
- Modify: `backend/tests/test_ai_tools.py`
- Modify: `backend/tests/test_ai_proposals.py`

**Interfaces:**
```python
WRITE_TOOL_NAMES = frozenset({
    "add_watchlist", "remove_watchlist", "upsert_note_memo", "add_note_entry",
    "upsert_position", "delete_position", "add_signal_panel", "remove_signal_panel",
})

def _upsert_position(db, user_id, args) -> dict: ...
def _delete_position(db, user_id, args) -> dict: ...
def _add_signal_panel(db, user_id, args) -> dict: ...
def _remove_signal_panel(db, user_id, args) -> dict: ...
# 均注册到 WRITE_HANDLERS；不进 TOOL_HANDLERS
```

- [ ] **Step 1: 写失败单测**

```python
# backend/tests/test_ai_write_positions.py
"""AI 持仓/信号写工具（mock repo，不打真库）。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.services import ai_tools
from app.services.ai_tools import execute_write_tool, summarize_write_tool


def test_summarize_new_write_tools() -> None:
    s = summarize_write_tool(
        "upsert_position",
        {"symbol": "600519.SSE", "cost_price": 100, "volume": 100, "buy_date": "2026-08-01"},
    )
    assert "持仓" in s and "600519" in s
    assert "删除持仓" in summarize_write_tool("delete_position", {"symbol": "600519.SSE"})
    assert "信号名单" in summarize_write_tool("add_signal_panel", {"symbol": "600519.SSE"})
    assert "移出信号名单" in summarize_write_tool("remove_signal_panel", {"symbol": "600519.SSE"})


def test_upsert_position_requires_watchlist() -> None:
    db = MagicMock()
    with (
        patch.object(ai_tools.watchlist_repo, "resolve_symbol_pair", return_value=("600519", "SSE")),
        patch.object(ai_tools, "positions_repo") as pref,
    ):
        # 懒导入场景：handler 内 from app.services import positions_repo
        # 故 patch 路径用 app.services.positions_repo
        pass


# 更稳妥：patch handler 所用模块路径
def test_upsert_not_in_watchlist() -> None:
    db = MagicMock()
    with (
        patch("app.services.ai_tools.watchlist_repo.resolve_symbol_pair", return_value=("600519", "SSE")),
        patch(
            "app.services.positions_repo.get_position",
            return_value=None,
        ),
        patch(
            "app.services.positions_repo.add_position",
            side_effect=HTTPException(status_code=400, detail="须先加入自选再录入持仓"),
        ),
    ):
        # 若 handler 通过 `from app.services import positions_repo` 局部导入，patch:
        # patch("app.services.positions_repo.add_position", ...)
        out = execute_write_tool(
            db,
            "u1",
            "upsert_position",
            {
                "symbol": "600519.SSE",
                "cost_price": 100,
                "volume": 100,
                "buy_date": "2026-08-01",
            },
        )
    assert isinstance(out, dict)
    assert "error" in out
    assert "自选" in str(out["error"])


def test_upsert_creates_when_missing() -> None:
    db = MagicMock()
    row = {
        "vt_symbol": "600519.SSE",
        "symbol": "600519",
        "exchange": "SSE",
        "cost_price": 100.0,
        "volume": 100,
        "buy_date": "2026-08-01",
    }
    with (
        patch("app.services.ai_tools.watchlist_repo.resolve_symbol_pair", return_value=("600519", "SSE")),
        patch("app.services.positions_repo.get_position", return_value=None),
        patch("app.services.positions_repo.add_position", return_value=row) as add,
        patch("app.services.positions_repo.update_position") as upd,
    ):
        out = execute_write_tool(
            db,
            "u1",
            "upsert_position",
            {
                "symbol": "600519.SSE",
                "cost_price": 100,
                "volume": 100,
                "buy_date": "2026-08-01",
            },
        )
    assert out.get("ok") is True
    assert out.get("action") == "created"
    add.assert_called_once()
    upd.assert_not_called()


def test_upsert_updates_when_exists() -> None:
    db = MagicMock()
    existing = {"vt_symbol": "600519.SSE", "symbol": "600519", "exchange": "SSE"}
    row = {**existing, "cost_price": 110.0, "volume": 200, "buy_date": "2026-08-01"}
    with (
        patch("app.services.ai_tools.watchlist_repo.resolve_symbol_pair", return_value=("600519", "SSE")),
        patch("app.services.positions_repo.get_position", return_value=existing),
        patch("app.services.positions_repo.update_position", return_value=row) as upd,
        patch("app.services.positions_repo.add_position") as add,
    ):
        out = execute_write_tool(
            db,
            "u1",
            "upsert_position",
            {
                "symbol": "600519.SSE",
                "cost_price": 110,
                "volume": 200,
                "buy_date": "2026-08-01",
            },
        )
    assert out.get("action") == "updated"
    upd.assert_called_once()
    add.assert_not_called()


def test_delete_position_missing() -> None:
    db = MagicMock()
    with (
        patch("app.services.ai_tools.watchlist_repo.resolve_symbol_pair", return_value=("600519", "SSE")),
        patch("app.services.positions_repo.delete_position", return_value=False),
    ):
        out = execute_write_tool(db, "u1", "delete_position", {"symbol": "600519.SSE"})
    assert "error" in out


def test_add_remove_signal_panel() -> None:
    db = MagicMock()
    with patch(
        "app.services.signal_panel_repo.add_symbol",
        return_value=["600519.SSE"],
    ):
        out = execute_write_tool(db, "u1", "add_signal_panel", {"symbol": "600519.SSE"})
    assert out.get("ok") is True
    assert "600519.SSE" in (out.get("symbols") or [])

    with patch(
        "app.services.signal_panel_repo.remove_symbol",
        side_effect=HTTPException(status_code=404, detail="不在信号名单中"),
    ):
        out2 = execute_write_tool(db, "u1", "remove_signal_panel", {"symbol": "600519.SSE"})
    assert "error" in out2
```

**实现提示（patch 路径）：** handler 内请使用**模块级** import（与 `_add_watchlist` 一致：`from app.services import positions_repo` 可在文件顶或函数内）。若函数内 `from app.services import positions_repo`，单测应 `patch("app.services.positions_repo.get_position", ...)`（patch 定义处）。上表两种写法以实现时 import 为准；**实现选定一种后，测试与之对齐**。推荐：

```python
# ai_tools.py 顶部附近
from app.services import positions_repo, signal_panel_repo
```

则单测 patch：`app.services.ai_tools.positions_repo.get_position` 等。

- [ ] **Step 2: 跑测确认失败**

```bash
cd /Users/xiezhigang/Projects/me/zak2/backend && python -m pytest tests/test_ai_write_positions.py -v
```

Expected: FAIL（工具未注册 / ImportError / assert）

- [ ] **Step 3: 实现 handlers**

在 `ai_tools.py`：

1. 扩展 `WRITE_TOOL_NAMES` 加入四名。  
2. 顶部增加 `from app.services import positions_repo, signal_panel_repo`（若尚未有）。  
3. 实现：

```python
def _upsert_position(db: Session, user_id: str, args: dict[str, Any]) -> Any:
    raw = str(args.get("symbol") or args.get("vt_symbol") or "").strip()
    if not raw:
        return {"error": "需要 symbol，例如 600519.SSE"}
    try:
        cost_price = float(args.get("cost_price"))
        volume = int(args.get("volume"))
    except (TypeError, ValueError):
        return {"error": "cost_price / volume 无效"}
    buy_date = str(args.get("buy_date") or "").strip()
    if not buy_date:
        return {"error": "需要 buy_date（YYYY-MM-DD）"}
    notes = str(args.get("notes") or "")
    plan_pct = args.get("plan_pct")
    if plan_pct is not None and plan_pct != "":
        try:
            plan_pct = float(plan_pct)
        except (TypeError, ValueError):
            return {"error": "plan_pct 无效"}
    else:
        plan_pct = None
    try:
        symbol, exchange = watchlist_repo.resolve_symbol_pair(raw, args.get("exchange"))
        existing = positions_repo.get_position(db, user_id, symbol, exchange)
        if existing:
            row = positions_repo.update_position(
                db,
                user_id,
                symbol=symbol,
                exchange=exchange,
                cost_price=cost_price,
                volume=volume,
                buy_date=buy_date,
                notes=notes,
                plan_pct=plan_pct,
            )
            action = "updated"
        else:
            row = positions_repo.add_position(
                db,
                user_id,
                symbol=symbol,
                exchange=exchange,
                cost_price=cost_price,
                volume=volume,
                buy_date=buy_date,
                notes=notes,
                plan_pct=plan_pct,
            )
            action = "created"
    except Exception as exc:  # noqa: BLE001
        return {"error": str(getattr(exc, "detail", None) or exc)}
    vt = str(row.get("vt_symbol") or to_vt_symbol(symbol, exchange))
    return {
        "ok": True,
        "action": action,
        "vt_symbol": vt,
        "cost_price": row.get("cost_price"),
        "volume": row.get("volume"),
        "buy_date": row.get("buy_date"),
    }


def _delete_position(db: Session, user_id: str, args: dict[str, Any]) -> Any:
    raw = str(args.get("symbol") or args.get("vt_symbol") or "").strip()
    if not raw:
        return {"error": "需要 symbol，例如 600519.SSE"}
    try:
        symbol, exchange = watchlist_repo.resolve_symbol_pair(raw, args.get("exchange"))
        ok = positions_repo.delete_position(db, user_id, symbol=symbol, exchange=exchange)
    except Exception as exc:  # noqa: BLE001
        return {"error": str(getattr(exc, "detail", None) or exc)}
    if not ok:
        return {"error": "持仓不存在"}
    return {"ok": True, "vt_symbol": to_vt_symbol(symbol, exchange), "removed": True}


def _add_signal_panel(db: Session, user_id: str, args: dict[str, Any]) -> Any:
    raw = str(args.get("symbol") or args.get("vt_symbol") or "").strip()
    if not raw:
        return {"error": "需要 symbol，例如 600519.SSE"}
    try:
        symbols = signal_panel_repo.add_symbol(db, user_id, raw)
    except Exception as exc:  # noqa: BLE001
        return {"error": str(getattr(exc, "detail", None) or exc)}
    return {"ok": True, "symbols": symbols}


def _remove_signal_panel(db: Session, user_id: str, args: dict[str, Any]) -> Any:
    raw = str(args.get("symbol") or args.get("vt_symbol") or "").strip()
    if not raw:
        return {"error": "需要 symbol，例如 600519.SSE"}
    try:
        symbols = signal_panel_repo.remove_symbol(db, user_id, raw)
    except Exception as exc:  # noqa: BLE001
        return {"error": str(getattr(exc, "detail", None) or exc)}
    return {"ok": True, "symbols": symbols}
```

4. `WRITE_HANDLERS` 注册四函数。  
5. `summarize_write_tool` 增加四分支（成本/数量用 args 原值即可）。  
6. `TOOL_DEFINITIONS` 追加四个 function schema（description 标明需确认；upsert 参数含 cost_price/volume/buy_date required）。

示例 definition（upsert）：

```python
{
    "type": "function",
    "function": {
        "name": "upsert_position",
        "description": "提议录入或更新持仓（须先在自选；需用户确认后生效）",
        "parameters": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string"},
                "vt_symbol": {"type": "string"},
                "exchange": {"type": "string"},
                "cost_price": {"type": "number"},
                "volume": {"type": "integer", "description": "100 股整手"},
                "buy_date": {"type": "string", "description": "YYYY-MM-DD"},
                "notes": {"type": "string"},
                "plan_pct": {"type": "number"},
            },
            "required": ["symbol", "cost_price", "volume", "buy_date"],
        },
    },
},
```

7. 更新 `test_ai_tools.py` 的 `write` 集合与 `names == {...}` 断言，纳入四新工具。  
8. 更新 `test_ai_proposals.py`：`WRITE_TOOL_NAMES` 期望集合；`test_summarize_write_tool` 追加新摘要断言。  
9. 修正 Step 1 单测的 patch 路径，与实际 import 一致。

- [ ] **Step 4: 跑测绿**

```bash
cd /Users/xiezhigang/Projects/me/zak2/backend && python -m pytest tests/test_ai_write_positions.py tests/test_ai_tools.py tests/test_ai_proposals.py -v
```

Expected: PASS

- [ ] **Step 5: Commit（仅用户要求时）**

```bash
git add backend/app/services/ai_tools.py backend/tests/test_ai_write_positions.py backend/tests/test_ai_tools.py backend/tests/test_ai_proposals.py
git commit -m "$(cat <<'EOF'
feat(ai): 确认卡写工具支持持仓与信号名单

EOF
)"
```

---

### Task 2: 文档 + 验收

**Files:**
- Modify: `docs/gap-vs-desktop.md`
- Modify: `docs/smoke-checklist.md`

- [ ] **Step 1: gap**

- 「流式 chat + 只读工具 + 写操作确认卡」行：补持仓 upsert/delete、信号名单增删  
- 「写操作工具 / MCP / Skills」行：写工具由 4 改为 **8**（原 4 + 持仓/信号 4）  
- 「建议下一刀」：可写「只读持仓/信号工具或其它」；不强调 Docker（用户已跳过）

- [ ] **Step 2: smoke**

`/ai` 条目追加：可提议 `upsert_position` / 信号名单写工具，确认卡后落库；亦可 `pytest tests/test_ai_write_positions.py`。

- [ ] **Step 3: 再跑相关测**

```bash
cd /Users/xiezhigang/Projects/me/zak2/backend && python -m pytest tests/test_ai_write_positions.py tests/test_ai_tools.py tests/test_ai_proposals.py -v
```

可选全量：`python -m pytest -q`  
前端无改：可不跑 `npm run build`。

- [ ] **Step 4: Commit（仅用户要求时）**

```bash
git add docs/gap-vs-desktop.md docs/smoke-checklist.md
git commit -m "$(cat <<'EOF'
docs: 记录 AI 持仓/信号写工具与 smoke 项

EOF
)"
```

---

## Spec coverage

| Spec | Task |
|------|------|
| upsert/delete/add/remove 四工具 + WRITE | 1 |
| 缺自选失败 / 确认卡复用 | 1（行为 + 既有拦截） |
| 集合断言 / summarize | 1 |
| gap / smoke | 2 |
| 计划页 / Docker / 只读 get_* / 自动加自选 | 非目标 |

## Placeholder scan

无 TBD；patch 路径以实现时模块级 import 为准（plan 已推荐顶部 import）。

# 拆超大文件（ai_tools / strategy_board）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 `app/services/ai/ai_tools.py`（844 行）与 `app/services/strategy/strategy_board.py`（609 行）按职责拆分为更小的子模块/子包，保持公开 API 与行为零变化。

**Architecture:** `ai_tools.py` 拆为子包 `app/services/ai/tools/`（`_common.py` + `read.py` + `skills.py` + `write.py`），`ai_tools.py` 保留为编排入口（`execute_tool`/`execute_write_tool`/`get_tool_definitions`）并聚合注册表。`strategy_board.py` 平铺拆为 `strategy_board_config.py`（常量/config key）与 `strategy_board_calc.py`（K 线加载/信号计算/持仓增强），原文件保留 `load_strategy_board` 主入口并 re-export 全部原模块级名字。`summarize_write_tool` 380 行 if 链重构为表驱动。

**Tech Stack:** Python、SQLAlchemy、FastAPI、pytest。

## Global Constraints

- **行为零变化**：REST/JWT/公开 API/算法/返回值一字不变；消费者 import 路径不变（`app.services.ai.ai_tools`、`app.services.strategy.strategy_board` 均保留全部原符号）
- **patch 兼容（strategy_board）**：`test_strategy_board.py` 用 `patch.object(strategy_board, "_load_daily_bars_map")` 等 19 处 patch **strategy_board 模块属性**，因此 `strategy_board.py` 必须 `from ...strategy_board_calc import _load_daily_bars_map, ...`（等从子模块导入的名字）作为模块级属性，让 `load_strategy_board` 通过模块全局名引用——patch 才生效
- **patch 路径更新（ai_tools）**：`test_ai_write_positions.py` 中 4 处 `patch("app.services.ai.ai_tools.watchlist_repo.resolve_symbol_pair")` 必须改为 `patch("app.services.ai.tools.write.watchlist_repo.resolve_symbol_pair")`（写 handler 已迁入 `write.py`，其引用 `write.py` 模块级 `watchlist_repo`）
- **依赖方向**：`strategy_board_config.py` 不依赖 `_calc`；`_calc` 依赖 `_config` 常量与 `bars_limit_for`/`parse_config_key`；`strategy_board.py` 依赖两者。禁止反向依赖（无循环导入）
- 拆分子模块只做**原样搬移 + import 调整**，不重写函数内部逻辑（唯一例外：`summarize_write_tool` 表驱动重构，行为逐分支等价）
- 保留各 handler 函数内延迟 import（如 `read.py` 中 `from app.services.ai import ai_read_tools`），不改动
- commit 简体中文 `<type>(<scope>): <简述>`
- 每个 commit 前跑相关测试绿；终验跑全量 `uv run pytest -q --tb=short`

---

### Task 1: ai_tools 子包骨架（`_common.py` + `read.py`）

**Files:**
- Create: `backend/app/services/ai/tools/__init__.py`
- Create: `backend/app/services/ai/tools/_common.py`
- Create: `backend/app/services/ai/tools/read.py`
- Modify: `backend/app/services/ai/ai_tools.py`（删除已迁出的 11 个只读 handler 与对应定义，聚合 `READ_HANDLERS`/`READ_DEFINITIONS`，从 `_common` 导入 `_truncate`/`_parse_args`）
- Test: `backend/tests/test_ai_tools_split.py`（新增）

**Interfaces:**
- Consumes: 无
- Produces:
  - `app.services.ai.tools._common`: `MAX_RESULT_CHARS: int = 6000`、`ToolHandler = Callable[[Session, str, dict[str, Any]], Any]`、`_truncate(payload: Any) -> str`、`_parse_args(arguments: dict[str, Any] | str | None) -> dict[str, Any]`
  - `app.services.ai.tools.read`: `READ_HANDLERS: dict[str, ToolHandler]`（11 键）、`READ_DEFINITIONS: list[dict[str, Any]]`（11 条，key 同 READ_HANDLERS）
  - `app.services.ai.ai_tools` 保留：`TOOL_HANDLERS`（本任务先 `{**READ_HANDLERS}`，Task 2 补全）、`TOOL_DEFINITIONS`（本任务先 `[*READ_DEFINITIONS]`，Task 2 补全）、`WRITE_TOOL_NAMES`、`execute_tool`、`execute_write_tool`、`get_tool_definitions`、`summarize_write_tool`（后两者 Task 2 起从 write 聚合）

- [ ] **Step 1: 写失败测试**

`backend/tests/test_ai_tools_split.py`：

```python
"""ai_tools 拆分子包结构回归：_common/read 符号归属。"""

from __future__ import annotations

from app.services.ai.tools._common import MAX_RESULT_CHARS, ToolHandler, _parse_args, _truncate
from app.services.ai.tools.read import READ_DEFINITIONS, READ_HANDLERS


def test_common_module_exports() -> None:
    assert MAX_RESULT_CHARS == 6000
    assert _parse_args(None) == {}
    assert _parse_args('{"a": 1}') == {"a": 1}
    assert callable(_truncate)
    assert callable(ToolHandler) is False or isinstance(ToolHandler, object)


def test_read_module_registers_only_read_tools() -> None:
    names = set(READ_HANDLERS)
    assert names == {
        "get_watchlist",
        "get_positions",
        "get_signal_panel",
        "get_trading_risk",
        "get_market_emotion",
        "get_recent_screening",
        "get_radar_snapshot",
        "list_note_symbols",
        "get_stock_notes",
        "get_bars_summary",
        "get_recent_backtest",
    }
    assert {d["function"]["name"] for d in READ_DEFINITIONS} == names
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && uv run pytest tests/test_ai_tools_split.py -q --tb=short`
Expected: FAIL —— `ModuleNotFoundError: No module named 'app.services.ai.tools'`

- [ ] **Step 3: 创建 `_common.py`**

`backend/app/services/ai/tools/_common.py`：

```python
"""ai_tools 拆分子包：公共常量、截断与参数解析。"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from sqlalchemy.orm import Session

MAX_RESULT_CHARS = 6000

ToolHandler = Callable[[Session, str, dict[str, Any]], Any]


def _truncate(payload: Any) -> str:
    text = json.dumps(payload, ensure_ascii=False, default=str)
    if len(text) <= MAX_RESULT_CHARS:
        return text
    return text[: MAX_RESULT_CHARS - 20] + "…(truncated)"


def _parse_args(arguments: dict[str, Any] | str | None) -> dict[str, Any]:
    if arguments is None:
        return {}
    if isinstance(arguments, str):
        try:
            parsed = json.loads(arguments or "{}")
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}
    if isinstance(arguments, dict):
        return arguments
    return {}
```

- [ ] **Step 4: 创建 `read.py`（11 个只读 handler 原样搬移）**

`backend/app/services/ai/tools/read.py`：把原 `ai_tools.py` 中 11 个只读 handler（`_get_watchlist`、`_get_positions`、`_get_signal_panel`、`_get_trading_risk`、`_get_market_emotion`、`_get_recent_screening`、`_get_radar_snapshot`、`_list_note_symbols`、`_get_stock_notes`、`_get_bars_summary`、`_get_recent_backtest`）原样搬入，函数体**一字不改**（含函数内延迟 import `from app.services.ai import ai_read_tools`）。文件头：

```python
"""投研只读工具实现（ai_tools 拆分）。"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.domains.backtest import repository as backtest_repo
from app.domains.market import bars
from app.domains.watchlist import repository as watchlist_repo
from app.services.symbols import to_vt_symbol
from app.services.ai.tools._common import ToolHandler
```

文件尾追加注册表（只读 11 键）：

```python
READ_HANDLERS: dict[str, ToolHandler] = {
    "get_watchlist": _get_watchlist,
    "get_positions": _get_positions,
    "get_signal_panel": _get_signal_panel,
    "get_trading_risk": _get_trading_risk,
    "get_market_emotion": _get_market_emotion,
    "get_recent_screening": _get_recent_screening,
    "get_radar_snapshot": _get_radar_snapshot,
    "list_note_symbols": _list_note_symbols,
    "get_stock_notes": _get_stock_notes,
    "get_bars_summary": _get_bars_summary,
    "get_recent_backtest": _get_recent_backtest,
}

READ_DEFINITIONS: list[dict[str, Any]] = [
    # 原 ai_tools.py TOOL_DEFINITIONS 中 key ∈ READ_HANDLERS 的 11 条，内容原样搬移
]
```

> `READ_DEFINITIONS` 的 11 条 JSON 定义从原 `ai_tools.py` 的 `TOOL_DEFINITIONS` 列表**按 key 归属原样搬移**（`get_watchlist` … `get_recent_backtest`），不做任何编辑。

- [ ] **Step 5: 创建 `__init__.py`（子包聚合壳）**

`backend/app/services/ai/tools/__init__.py`：

```python
"""ai_tools 拆分子包：只读 / 技能 / 写工具 + 公共工具。"""

from app.services.ai.tools._common import MAX_RESULT_CHARS, ToolHandler, _parse_args, _truncate
from app.services.ai.tools.read import READ_DEFINITIONS, READ_HANDLERS

__all__ = [
    "MAX_RESULT_CHARS",
    "READ_DEFINITIONS",
    "READ_HANDLERS",
    "ToolHandler",
    "_parse_args",
    "_truncate",
]
```

- [ ] **Step 6: 收敛 `ai_tools.py`（删除已迁出代码 + 聚合）**

编辑 `backend/app/services/ai/ai_tools.py`：

1. 删除 11 个只读 handler 函数体（`_get_watchlist` … `_get_recent_backtest`），删除顶部 `from app.domains.backtest import repository as backtest_repo`、`from app.domains.market import bars`、`from app.services.symbols import to_vt_symbol`（仅 read 使用；写 handler 还在本文件，Task 2 迁出后再清）
2. 顶部 import 改为：

```python
from __future__ import annotations

import json
import logging
from typing import Any, cast

from sqlalchemy.orm import Session

from app.domains.content import notes
from app.domains.watchlist import positions_repo
from app.domains.watchlist import repository as watchlist_repo
from app.domains.watchlist import signal_panel_repo
from app.services.ai.tools._common import MAX_RESULT_CHARS, ToolHandler, _parse_args, _truncate
from app.services.ai.tools.read import READ_DEFINITIONS, READ_HANDLERS
```

3. `WRITE_TOOL_NAMES` 保留在本文件（Task 2 迁出），`TOOL_HANDLERS`/`TOOL_DEFINITIONS` 改为：

```python
TOOL_HANDLERS: dict[str, ToolHandler] = {**READ_HANDLERS}
TOOL_DEFINITIONS: list[dict[str, Any]] = [*READ_DEFINITIONS]
```

> 本任务阶段 `TOOL_HANDLERS`/`TOOL_DEFINITIONS` 只含只读（Skill/写工具还在本文件，Task 2 收敛后补全）；`get_tool_definitions()`、`execute_tool`、`execute_write_tool`、`summarize_write_tool` 原样保留。

- [ ] **Step 7: 运行测试确认通过**

Run: `cd backend && uv run pytest tests/test_ai_tools_split.py tests/test_ai_tools.py tests/test_ai_read_tools.py -q --tb=short`
Expected: PASS（全部绿，含既有 `test_ai_tools.py` 的 `test_tools_registered`——注意此时它断言的完整工具集可能因 Task 2 未完成而少 skills/write；若 FAIL 属预期，Task 2 完成后恢复）

- [ ] **Step 8: Commit**

```bash
git add backend/app/services/ai/tools/ backend/app/services/ai/ai_tools.py backend/tests/test_ai_tools_split.py
git commit -m "refactor(ai): ai_tools 只读工具迁入 tools 子包 read 模块"
```

---

### Task 2: skills + write 子模块 + summarize 表驱动重构 + ai_tools 收敛编排

**Files:**
- Create: `backend/app/services/ai/tools/skills.py`
- Create: `backend/app/services/ai/tools/write.py`
- Modify: `backend/app/services/ai/tools/__init__.py`（聚合全量）
- Modify: `backend/app/services/ai/ai_tools.py`（删除 skills/write 函数，收敛为纯编排 + 聚合注册表）
- Modify: `backend/tests/test_ai_write_positions.py`（4 处 patch 路径）
- Modify: `backend/tests/test_ai_tools_split.py`（补 skills/write 断言）
- Test: `backend/tests/test_ai_tools_split.py`

**Interfaces:**
- Consumes: Task 1 的 `_common`/`read`
- Produces:
  - `app.services.ai.tools.skills`: `SKILL_HANDLERS: dict[str, ToolHandler]`（3 键）、`SKILL_DEFINITIONS: list[dict[str, Any]]`（3 条）
  - `app.services.ai.tools.write`: `WRITE_TOOL_NAMES: frozenset[str]`（8 键）、`WRITE_HANDLERS: dict[str, ToolHandler]`（8 键）、`WRITE_DEFINITIONS: list[dict[str, Any]]`（8 条）、`summarize_write_tool(name: str, args: dict[str, Any]) -> str`（表驱动）
  - `ai_tools.py` 最终形态：仅保留 `logger`、`get_tool_definitions`、`execute_write_tool`、`_mcp_tool_definitions`、`_execute_mcp_tool`、`execute_tool`，聚合 `TOOL_HANDLERS = {**READ_HANDLERS, **SKILL_HANDLERS, **WRITE_HANDLERS}`、`TOOL_DEFINITIONS = [*READ_DEFINITIONS, *SKILL_DEFINITIONS, *WRITE_DEFINITIONS]`，并 re-export `WRITE_TOOL_NAMES`、`summarize_write_tool`、`_parse_args`、`MAX_RESULT_CHARS`

- [ ] **Step 1: 扩展失败测试**

`backend/tests/test_ai_tools_split.py` 追加：

```python
from app.services.ai.tools.skills import SKILL_DEFINITIONS, SKILL_HANDLERS
from app.services.ai.tools.write import (
    WRITE_DEFINITIONS,
    WRITE_HANDLERS,
    WRITE_TOOL_NAMES,
    summarize_write_tool,
)


def test_skills_module_registers_three() -> None:
    assert set(SKILL_HANDLERS) == {"list_skills", "read_skill", "run_skill"}
    assert {d["function"]["name"] for d in SKILL_DEFINITIONS} == set(SKILL_HANDLERS)


def test_write_module_registers_eight() -> None:
    assert set(WRITE_HANDLERS) == set(WRITE_TOOL_NAMES) == {
        "add_watchlist",
        "remove_watchlist",
        "upsert_note_memo",
        "add_note_entry",
        "upsert_position",
        "delete_position",
        "add_signal_panel",
        "remove_signal_panel",
    }
    assert {d["function"]["name"] for d in WRITE_DEFINITIONS} == set(WRITE_TOOL_NAMES)


def test_ai_tools_aggregates_all() -> None:
    from app.services.ai import ai_tools

    read = set(READ_HANDLERS) | set(SKILL_HANDLERS) | set(WRITE_HANDLERS)
    assert set(ai_tools.TOOL_HANDLERS) == read
    assert {d["function"]["name"] for d in ai_tools.TOOL_DEFINITIONS} == read


def test_summarize_table_driven_equivalence() -> None:
    assert summarize_write_tool("no_such", {}) == "no_such"
    assert "加自选" in summarize_write_tool("add_watchlist", {"symbol": "600519.SSE", "name": "茅台"})
    assert "写备忘" in summarize_write_tool("upsert_note_memo", {"vt_symbol": "600519.SSE", "body": "观察"})
    assert "成本100 数量100" in summarize_write_tool(
        "upsert_position",
        {"symbol": "600519.SSE", "cost_price": 100, "volume": 100},
    )
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && uv run pytest tests/test_ai_tools_split.py -q --tb=short`
Expected: FAIL —— `ModuleNotFoundError: No module named 'app.services.ai.tools.skills'`

- [ ] **Step 3: 创建 `skills.py`**

`backend/app/services/ai/tools/skills.py`：把原 `ai_tools.py` 中 `_list_skills`、`_read_skill`、`_run_skill` 原样搬入（函数体一字不改，保留函数内延迟 import `from app.services.ai import skills_catalog` 与 `from app.services.ai.skill_runtime import ...`）。文件头与注册表：

```python
"""内置投研技能工具（ai_tools 拆分）。"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.services.ai.tools._common import ToolHandler


def _list_skills(db: Session, user_id: str, args: dict[str, Any]) -> Any:
    # 原样搬移
    ...


def _read_skill(db: Session, user_id: str, args: dict[str, Any]) -> Any:
    # 原样搬移
    ...


def _run_skill(db: Session, user_id: str, args: dict[str, Any]) -> Any:
    # 原样搬移
    ...


SKILL_HANDLERS: dict[str, ToolHandler] = {
    "list_skills": _list_skills,
    "read_skill": _read_skill,
    "run_skill": _run_skill,
}

SKILL_DEFINITIONS: list[dict[str, Any]] = [
    # 原 ai_tools.py TOOL_DEFINITIONS 中 list_skills/read_skill/run_skill 三条，原样搬移
]
```

- [ ] **Step 4: 创建 `write.py`（8 个写 handler + 表驱动 summarize）**

`backend/app/services/ai/tools/write.py`：把原 `ai_tools.py` 中 8 个写 handler（`_add_watchlist`、`_remove_watchlist`、`_upsert_note_memo`、`_add_note_entry`、`_upsert_position`、`_delete_position`、`_add_signal_panel`、`_remove_signal_panel`）原样搬入。文件头：

```python
"""投研写工具实现（需确认后落库，ai_tools 拆分）。"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any, cast

from sqlalchemy.orm import Session

from app.domains.content import notes
from app.domains.watchlist import positions_repo
from app.domains.watchlist import repository as watchlist_repo
from app.domains.watchlist import signal_panel_repo
from app.services.symbols import to_vt_symbol
from app.services.ai.tools._common import ToolHandler

logger = logging.getLogger(__name__)

WRITE_TOOL_NAMES = frozenset(
    {
        "add_watchlist",
        "remove_watchlist",
        "upsert_note_memo",
        "add_note_entry",
        "upsert_position",
        "delete_position",
        "add_signal_panel",
        "remove_signal_panel",
    }
)
```

文件尾注册表：

```python
WRITE_HANDLERS: dict[str, ToolHandler] = {
    "add_watchlist": _add_watchlist,
    "remove_watchlist": _remove_watchlist,
    "upsert_note_memo": _upsert_note_memo,
    "add_note_entry": _add_note_entry,
    "upsert_position": _upsert_position,
    "delete_position": _delete_position,
    "add_signal_panel": _add_signal_panel,
    "remove_signal_panel": _remove_signal_panel,
}

WRITE_DEFINITIONS: list[dict[str, Any]] = [
    # 原 ai_tools.py TOOL_DEFINITIONS 中 add_watchlist … remove_signal_panel 八条，原样搬移
]
```

`summarize_write_tool` 用**表驱动重构**（行为逐分支等价于原 if 链；原逻辑：`add_watchlist` 取 `symbol or vt_symbol`，`upsert_note_memo`/`add_note_entry` 取 `vt_symbol or symbol`，其余取 `symbol or vt_symbol`；body 预览 40 字加 `…`；`upsert_position` 打印 `成本{cost} 数量{vol}`；未知名返回 `name`）：

```python
_SummaryFn = Callable[[dict[str, Any]], str]


def _sym(args: dict[str, Any], *, vt_first: bool = False) -> str:
    first, second = ("vt_symbol", "symbol") if vt_first else ("symbol", "vt_symbol")
    return str(args.get(first) or args.get(second) or "").strip() or "?"


def _preview(raw: Any, limit: int = 40) -> str:
    body = str(raw or "").strip().replace("\n", " ")
    return body[:limit] + ("…" if len(body) > limit else "")


_WRITE_SUMMARIES: dict[str, _SummaryFn] = {
    "add_watchlist": lambda a: f"加自选：{_sym(a)}" + (f"（{a.get('name', '').strip()}）" if a.get("name", "").strip() else ""),
    "remove_watchlist": lambda a: f"删自选：{_sym(a)}",
    "upsert_note_memo": lambda a: f"写备忘：{_sym(a, vt_first=True)} — {_preview(a.get('body'))}",
    "add_note_entry": lambda a: f"记流水：{_sym(a, vt_first=True)} — {_preview(a.get('body'))}",
    "upsert_position": lambda a: f"录入/更新持仓：{_sym(a)} 成本{a.get('cost_price')} 数量{a.get('volume')}",
    "delete_position": lambda a: f"删除持仓：{_sym(a)}",
    "add_signal_panel": lambda a: f"加入信号名单：{_sym(a)}",
    "remove_signal_panel": lambda a: f"移出信号名单：{_sym(a)}",
}


def summarize_write_tool(name: str, args: dict[str, Any]) -> str:
    fn = _WRITE_SUMMARIES.get(name)
    return fn(args) if fn else name
```

> 与原有测试断言完全兼容：`test_ai_proposals.py::test_summarize_write_tool`、`test_ai_write_positions.py::test_summarize_new_write_tools` 只断言中文前缀与 `600519`/`100` 子串，且 `upsert_position` 的 `cost_price=100, volume=100` 输出含 `成本100 数量100`。

- [ ] **Step 5: 更新 `__init__.py` 聚合全量**

`backend/app/services/ai/tools/__init__.py`：

```python
"""ai_tools 拆分子包：只读 / 技能 / 写工具 + 公共工具。"""

from app.services.ai.tools._common import MAX_RESULT_CHARS, ToolHandler, _parse_args, _truncate
from app.services.ai.tools.read import READ_DEFINITIONS, READ_HANDLERS
from app.services.ai.tools.skills import SKILL_DEFINITIONS, SKILL_HANDLERS
from app.services.ai.tools.write import (
    WRITE_DEFINITIONS,
    WRITE_HANDLERS,
    WRITE_TOOL_NAMES,
    summarize_write_tool,
)

__all__ = [
    "MAX_RESULT_CHARS",
    "READ_DEFINITIONS",
    "READ_HANDLERS",
    "SKILL_DEFINITIONS",
    "SKILL_HANDLERS",
    "ToolHandler",
    "WRITE_DEFINITIONS",
    "WRITE_HANDLERS",
    "WRITE_TOOL_NAMES",
    "_parse_args",
    "_truncate",
    "summarize_write_tool",
]
```

- [ ] **Step 6: 收敛 `ai_tools.py` 为纯编排入口**

编辑 `backend/app/services/ai/ai_tools.py`：

1. 删除 `_list_skills`/`_read_skill`/`_run_skill` 与 8 个写 handler、`WRITE_TOOL_NAMES`、`summarize_write_tool`、原 `TOOL_HANDLERS`/`WRITE_HANDLERS`/`TOOL_DEFINITIONS` 字面量
2. 删除顶部不再使用的 import（`notes`、`positions_repo`、`signal_panel_repo`、`cast`、`json` 仅 `_parse_args` 用但已迁 `_common`）
3. 顶部 import 与聚合改为：

```python
"""投研工具编排入口：只读 + 需确认的写操作，供 Agent tool-calling。

实现拆分为 app/services/ai/tools/ 子包，本模块聚合注册表并提供执行编排。
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from app.services.ai.tools._common import MAX_RESULT_CHARS, ToolHandler, _parse_args, _truncate
from app.services.ai.tools.read import READ_DEFINITIONS, READ_HANDLERS
from app.services.ai.tools.skills import SKILL_DEFINITIONS, SKILL_HANDLERS
from app.services.ai.tools.write import (
    WRITE_DEFINITIONS,
    WRITE_HANDLERS,
    WRITE_TOOL_NAMES,
    summarize_write_tool,
)

logger = logging.getLogger(__name__)

TOOL_HANDLERS: dict[str, ToolHandler] = {**READ_HANDLERS, **SKILL_HANDLERS, **WRITE_HANDLERS}
TOOL_DEFINITIONS: list[dict[str, Any]] = [*READ_DEFINITIONS, *SKILL_DEFINITIONS, *WRITE_DEFINITIONS]
```

4. 保留原样不动：`get_tool_definitions`、`execute_write_tool`、`_mcp_tool_definitions`、`_execute_mcp_tool`、`execute_tool`

> `execute_tool` 引用 `WRITE_TOOL_NAMES`（已 import）、`_parse_args`（已 import）、`_truncate`（已 import）、`_execute_mcp_tool`（同文件）——均可用。`execute_write_tool` 引用 `WRITE_HANDLERS`/`_parse_args`——可用。

- [ ] **Step 7: 更新 patch 路径（4 处）**

`backend/tests/test_ai_write_positions.py` 中全部 4 处：

```python
patch("app.services.ai.ai_tools.watchlist_repo.resolve_symbol_pair", return_value=("600519", "SSE")),
```

改为：

```python
patch("app.services.ai.tools.write.watchlist_repo.resolve_symbol_pair", return_value=("600519", "SSE")),
```

（可全局替换 `"app.services.ai.ai_tools.watchlist_repo"` → `"app.services.ai.tools.write.watchlist_repo"`）

- [ ] **Step 8: 运行测试确认通过**

Run: `cd backend && uv run pytest tests/test_ai_tools_split.py tests/test_ai_tools.py tests/test_ai_read_tools.py tests/test_ai_proposals.py tests/test_ai_write_positions.py -q --tb=short`
Expected: PASS（全部绿，`test_tools_registered` 恢复断言完整 22 工具集）

- [ ] **Step 9: Commit**

```bash
git add backend/app/services/ai/tools/ backend/app/services/ai/ai_tools.py backend/tests/test_ai_tools_split.py backend/tests/test_ai_write_positions.py
git commit -m "refactor(ai): ai_tools 拆分完成并表驱动化 summarize_write_tool"
```

---

### Task 3: strategy_board 平铺拆分（config + calc）

**Files:**
- Create: `backend/app/services/strategy/strategy_board_config.py`
- Create: `backend/app/services/strategy/strategy_board_calc.py`
- Modify: `backend/app/services/strategy/strategy_board.py`（删除已迁出函数，保留 `load_strategy_board` + `_mode_note`，从子模块导入并在模块级聚合全部原名字）
- Test: `backend/tests/test_strategy_board_split.py`（新增）

**Interfaces:**
- Consumes: Task 1/2 无关；依赖 `app.services.strategy.strategy_signal_ma`、`strategy_signal_extra`、`position_risk_tags`（不变）
- Produces:
  - `strategy_board_config.py`: `DEFAULT_CONFIG_KEY`、`SIGNAL_MODE_*`、`ALL_SIGNAL_MODES`、`DEFAULT_DOUBLE_MA_FAST/SLOW`、`BAR_LIMIT`、`bars_limit_for(mode, config_key) -> int`、`resolve_config_key(db, user_id, override=None) -> str`、`double_ma_config_key`/`trend_ma_config_key`/`medium_swing_config_key`/`donchian_config_key`/`rsi_reversal_config_key`/`bollinger_config_key`/`ma_band_config_key`/`atr_breakout_config_key`、`_pref_fast_slow(db, user_id) -> tuple[int, int]`、`resolve_board_config_key(db, user_id, *, signal_mode, override) -> str`
  - `strategy_board_calc.py`: `_safe_float`、`_parse_payload`、`_load_daily_bars_map`、`_compute_snapshot`、`_t1_locked`、`_signal_label`、`enrich_position_risk`、`_pack_signal_row`
  - `strategy_board.py` 保留模块级名字（**patch 兼容关键**）：`load_strategy_board`、`_mode_note`、`get_quote_store`、`repo`、`signal_panel_repo`、`positions_repo`、`load_trading_risk_prefs`、`compute_actual_position_pct`、`to_tf_symbol`、`to_vt_symbol`、以及从子模块 import 的全部符号（`DEFAULT_CONFIG_KEY`、`SIGNAL_MODE_*`、`ALL_SIGNAL_MODES`、`bars_limit_for`、`resolve_config_key`、`resolve_board_config_key`、`_safe_float`、`_parse_payload`、`_load_daily_bars_map`、`_compute_snapshot`、`_t1_locked`、`_signal_label`、`enrich_position_risk`、`_pack_signal_row`）

- [ ] **Step 1: 写失败测试**

`backend/tests/test_strategy_board_split.py`：

```python
"""strategy_board 平铺拆分结构回归：config/calc 符号归属 + 原模块聚合。"""

from __future__ import annotations

from app.services.strategy.strategy_board_calc import (
    _load_daily_bars_map,
    _pack_signal_row,
    _parse_payload,
    _t1_locked,
    enrich_position_risk,
)
from app.services.strategy.strategy_board_config import (
    DEFAULT_CONFIG_KEY,
    ALL_SIGNAL_MODES,
    bars_limit_for,
    resolve_board_config_key,
    resolve_config_key,
)


def test_config_module_exports() -> None:
    assert DEFAULT_CONFIG_KEY.startswith("AshareShortBreakoutStrategy")
    assert len(ALL_SIGNAL_MODES) == 9
    assert callable(resolve_config_key)
    assert callable(resolve_board_config_key)
    assert callable(bars_limit_for)


def test_calc_module_exports() -> None:
    assert callable(_load_daily_bars_map)
    assert callable(_pack_signal_row)
    assert callable(_parse_payload)
    assert callable(_t1_locked)
    assert callable(enrich_position_risk)


def test_strategy_board_still_exposes_all() -> None:
    from app.services.strategy import strategy_board as sb

    for name in (
        "DEFAULT_CONFIG_KEY",
        "SIGNAL_MODE_HEURISTIC",
        "ALL_SIGNAL_MODES",
        "bars_limit_for",
        "resolve_config_key",
        "resolve_board_config_key",
        "_safe_float",
        "_parse_payload",
        "_load_daily_bars_map",
        "_compute_snapshot",
        "_t1_locked",
        "_signal_label",
        "enrich_position_risk",
        "_pack_signal_row",
        "load_strategy_board",
        "get_quote_store",
        "repo",
        "signal_panel_repo",
        "positions_repo",
    ):
        assert hasattr(sb, name), name
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && uv run pytest tests/test_strategy_board_split.py -q --tb=short`
Expected: FAIL —— `ModuleNotFoundError: No module named 'app.services.strategy.strategy_board_config'`

- [ ] **Step 3: 创建 `strategy_board_config.py`**

`backend/app/services/strategy/strategy_board_config.py`：把原 `strategy_board.py` 的常量区（`DEFAULT_CONFIG_KEY` 至 `BAR_LIMIT`）与函数 `bars_limit_for`、`resolve_config_key`、`double_ma_config_key` … `atr_breakout_config_key`、`_pref_fast_slow`、`resolve_board_config_key` 原样搬入。文件头：

```python
"""自选策略看板：模式常量与 config_key 解析（strategy_board 拆分）。"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.strategy.strategy_signal_ma import parse_config_key

DEFAULT_CONFIG_KEY = "AshareShortBreakoutStrategy:5:10"
SIGNAL_MODE_HEURISTIC = "heuristic_v2"
SIGNAL_MODE_DOUBLE_MA = "double_ma"
SIGNAL_MODE_TREND_MA = "trend_ma"
SIGNAL_MODE_MEDIUM_SWING = "medium_swing"
SIGNAL_MODE_DONCHIAN = "donchian"
SIGNAL_MODE_RSI_REVERSAL = "rsi_reversal"
SIGNAL_MODE_BOLLINGER = "bollinger"
SIGNAL_MODE_MA_BAND = "ma_band"
SIGNAL_MODE_ATR_BREAKOUT = "atr_breakout"
ALL_SIGNAL_MODES = frozenset(
    {
        SIGNAL_MODE_HEURISTIC,
        SIGNAL_MODE_DOUBLE_MA,
        SIGNAL_MODE_TREND_MA,
        SIGNAL_MODE_MEDIUM_SWING,
        SIGNAL_MODE_DONCHIAN,
        SIGNAL_MODE_RSI_REVERSAL,
        SIGNAL_MODE_BOLLINGER,
        SIGNAL_MODE_MA_BAND,
        SIGNAL_MODE_ATR_BREAKOUT,
    }
)
DEFAULT_DOUBLE_MA_FAST = 5
DEFAULT_DOUBLE_MA_SLOW = 20
BAR_LIMIT = 120
```

> 函数体全部**原样搬移**（含 `trend_ma_config_key` 等函数内的延迟 import）。注意 `bars_limit_for` 与 `resolve_config_key`/`_pref_fast_slow` 原样搬入即可（它们引用本文件常量与 `parse_config_key`，已 import）。`SIGNAL_MODE_*` 常量不再从 `_config` 之外的模块 import（原文件就是本文件内定义）。

- [ ] **Step 4: 创建 `strategy_board_calc.py`**

`backend/app/services/strategy/strategy_board_calc.py`：把原 `strategy_board.py` 的 `_safe_float`、`_parse_payload`、`_load_daily_bars_map`、`_compute_snapshot`、`_t1_locked`、`_signal_label`、`enrich_position_risk`、`_pack_signal_row` 原样搬入。文件头：

```python
"""自选策略看板：日 K 加载、信号计算与持仓增强（strategy_board 拆分）。"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.core.time import china_today
from app.models.bars import DbBarData
from app.services.symbols import normalize_exchange, to_vt_symbol
from app.services.strategy.position_risk_tags import compute_position_risk_tags, primary_risk_tag
from app.services.strategy.strategy_signal_extra import (
    compute_atr_breakout_signal,
    compute_bollinger_signal,
    compute_donchian_signal,
    compute_ma_band_signal,
    compute_rsi_reversal_signal,
)
from app.services.strategy.strategy_signal_ma import (
    compute_double_ma_signal,
    compute_ma_signal,
    compute_medium_swing_signal,
    compute_trend_ma_signal,
    parse_config_key,
)
from app.services.strategy.strategy_board_config import (
    BAR_LIMIT,
    DEFAULT_DOUBLE_MA_FAST,
    DEFAULT_DOUBLE_MA_SLOW,
    SIGNAL_MODE_ATR_BREAKOUT,
    SIGNAL_MODE_BOLLINGER,
    SIGNAL_MODE_DONCHIAN,
    SIGNAL_MODE_DOUBLE_MA,
    SIGNAL_MODE_MA_BAND,
    SIGNAL_MODE_MEDIUM_SWING,
    SIGNAL_MODE_RSI_REVERSAL,
    SIGNAL_MODE_TREND_MA,
)
```

> 函数体全部**原样搬移**。`_compute_snapshot` 引用的 `SIGNAL_MODE_*`/`DEFAULT_DOUBLE_MA_*` 来自 `_config`（已 import）；`_load_daily_bars_map` 引用 `DbBarData`/`normalize_exchange`/`to_vt_symbol`/`BAR_LIMIT`（已 import）。**不引入对 `strategy_board.py` 的任何 import（无循环）。**

- [ ] **Step 5: 收敛 `strategy_board.py`**

编辑 `backend/app/services/strategy/strategy_board.py`：

1. 删除常量区（`DEFAULT_CONFIG_KEY` … `BAR_LIMIT`）与 `bars_limit_for`、`resolve_config_key`、`*_config_key`、`_pref_fast_slow`、`resolve_board_config_key`、`_safe_float`、`_parse_payload`、`_load_daily_bars_map`、`_compute_snapshot`、`_t1_locked`、`_signal_label`、`enrich_position_risk`、`_pack_signal_row`
2. 顶部 import 改为：

```python
"""自选策略看盘：看板请求时实时按日 K 计算信号（不再依赖预热缓存）。

config 解析见 strategy_board_config，K 线/信号计算见 strategy_board_calc。
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.domains.market.quotes import get_quote_store
from app.domains.watchlist import positions_repo
from app.domains.watchlist import repository as repo
from app.domains.watchlist import signal_panel_repo
from app.domains.watchlist.trading_risk import (
    compute_actual_position_pct,
    load_trading_risk_prefs,
)
from app.services.symbols import to_tf_symbol, to_vt_symbol
from app.services.strategy.strategy_board_calc import (
    _compute_snapshot,
    _load_daily_bars_map,
    _pack_signal_row,
    _parse_payload,
    _safe_float,
    _signal_label,
    _t1_locked,
    enrich_position_risk,
)
from app.services.strategy.strategy_board_config import (
    ALL_SIGNAL_MODES,
    DEFAULT_CONFIG_KEY,
    DEFAULT_DOUBLE_MA_FAST,
    DEFAULT_DOUBLE_MA_SLOW,
    SIGNAL_MODE_ATR_BREAKOUT,
    SIGNAL_MODE_BOLLINGER,
    SIGNAL_MODE_DONCHIAN,
    SIGNAL_MODE_DOUBLE_MA,
    SIGNAL_MODE_HEURISTIC,
    SIGNAL_MODE_MA_BAND,
    SIGNAL_MODE_MEDIUM_SWING,
    SIGNAL_MODE_RSI_REVERSAL,
    SIGNAL_MODE_TREND_MA,
    bars_limit_for,
    resolve_board_config_key,
    resolve_config_key,
)
```

3. 保留 `load_strategy_board` 与 `_mode_note` 函数体**原样不动**

> 兼容验证：`load_strategy_board` 内引用的全部符号现在都是本模块级名字（`_load_daily_bars_map`/`_compute_snapshot`/`_pack_signal_row`/`_t1_locked`/`_signal_label`/`_safe_float`/`enrich_position_risk`/`bars_limit_for`/`resolve_board_config_key`/`_mode_note`/`ALL_SIGNAL_MODES`/`SIGNAL_MODE_*` 均从子模块 import）——`test_strategy_board.py` 的 19 处 `patch.object(strategy_board, ...)` 全部命中；`repo`/`signal_panel_repo`/`positions_repo`/`get_quote_store` 均为本模块属性——patch 命中。`DEFAULT_DOUBLE_MA_FAST/SLOW`、`DEFAULT_CONFIG_KEY` 等被 `test_strategy_board.py` 顶部 import 的符号也由模块级 import 提供。

- [ ] **Step 6: 运行测试确认通过**

Run: `cd backend && uv run pytest tests/test_strategy_board_split.py tests/test_strategy_board.py tests/test_ai_read_tools.py -q --tb=short`
Expected: PASS（全部绿；`test_strategy_board.py` 19 处 patch 与 config/calc 测试原样通过）

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/strategy/ backend/tests/test_strategy_board_split.py
git commit -m "refactor(strategy): strategy_board 按 config/calc 平铺拆分"
```

---

### Task 4: 文档 + 终验

**Files:**
- Modify: `docs/architecture-p1.md`
- 终验（不产生新测试文件）

- [ ] **Step 1: 更新架构文档**

`docs/architecture-p1.md` 结构段落（第 9 行附近）追加一句：

> `app/services/ai/ai_tools.py` 已拆为 `app/services/ai/tools/` 子包（read/skills/write）；`app/services/strategy/strategy_board.py` 已拆为 `strategy_board_config.py` + `strategy_board_calc.py`，原模块保留编排入口与聚合。

- [ ] **Step 2: 全量回归**

Run: `cd backend && uv run pytest -q --tb=short`
Expected: PASS（~732+ collected，全绿）

- [ ] **Step 3: import 冒烟**

Run:

```bash
cd backend && uv run python -c "
import app.main
from app.services.ai import ai_tools
from app.services.ai.ai_tools import (TOOL_HANDLERS, TOOL_DEFINITIONS, WRITE_TOOL_NAMES, _parse_args, execute_tool, execute_write_tool, get_tool_definitions, summarize_write_tool)
from app.services.ai.tools import READ_HANDLERS, SKILL_HANDLERS, WRITE_HANDLERS
from app.services.strategy import strategy_board
from app.services.strategy.strategy_board import load_strategy_board, DEFAULT_CONFIG_KEY, _pack_signal_row, _parse_payload, _t1_locked, enrich_position_risk, resolve_config_key, _load_daily_bars_map
assert len(TOOL_HANDLERS) == 22 and len(TOOL_DEFINITIONS) == 22
assert len(READ_HANDLERS) == 11 and len(SKILL_HANDLERS) == 3 and len(WRITE_HANDLERS) == 8
print('OK')
"
```

Expected: `OK`

- [ ] **Step 4: 行数验收**

Run: `wc -l backend/app/services/ai/ai_tools.py backend/app/services/strategy/strategy_board.py`
Expected: `ai_tools.py` ≤ ~120、`strategy_board.py` ≤ ~230（原先 844/609）

- [ ] **Step 5: Commit**

```bash
git add docs/architecture-p1.md
git commit -m "docs(backend): 补充 ai_tools 子包与 strategy_board 拆分说明"
```

---

## Self-Review

**Spec coverage 核对：**
- 「ai_tools 子包 read/skills/write/_common/__init__」→ Task 1/2 ✓
- 「ai_tools.py 保留编排入口（execute_tool/execute_write_tool/get_tool_definitions）」→ Task 2 Step 6 ✓
- 「strategy_board 平铺 config/calc，原文件保留 load_strategy_board」→ Task 3 ✓
- 「summarize_write_tool 表驱动重构」→ Task 2 Step 4 ✓（含 `vt_first` 区分 memo/entry 的 `vt_symbol or symbol` 原语义）
- 「行为零变化 + 消费者 import 不变」→ 模块级聚合 + patch 路径更新说明 ✓
- 「测试兜底」→ Task 1/2/3 结构回归测试 + 全量回归 ✓
- 「文档更新」→ Task 4 ✓

**Placeholder scan：** 无 TBD/「类似 Task N」；各搬移函数明确「原样搬移」，表驱动重构给了完整新代码。

**Type consistency：** `READ_HANDLERS`/`SKILL_HANDLERS`/`WRITE_HANDLERS`/`READ_DEFINITIONS` 等名称在 Task 1-2 定义与 Task 2 聚合处一致；`strategy_board_config`/`strategy_board_calc` 符号在 Task 3 定义与 `strategy_board.py` import 及 split 测试一致；`summarize_write_tool` 签名 `(name, args) -> str` 一致。

**已知注意点：**
- Task 1 Step 7 期间 `test_tools_registered` 可能暂时 FAIL（skills/write 尚未聚合），属预期；Task 2 Step 8 恢复全绿。若希望每个 commit 全绿，可将 Task 1/2 合并执行后再 commit，但按计划拆分 commit 更利于 review。

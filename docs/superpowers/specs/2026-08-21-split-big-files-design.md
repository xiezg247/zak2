# 拆超大文件（ai_tools / strategy_board）设计

日期：2026-08-21

## 背景

对照主 spec（backend-architecture-refactor-design）「横切能力」表的「拆超大文件（Phase 3+ 随域）」项，两个文件已明显超重：

- `app/services/ai/ai_tools.py`：**844 行**——14 个只读工具 + 8 个写工具 + 22 条 MCP/工具定义 + 380 行 `summarize_write_tool` if 链 + 编排
- `app/services/strategy/strategy_board.py`：**609 行**——常量 + config key 解析 + 信号计算 + 看板组装

两者均被多个消费者引用（ai_tools 8 处、strategy_board 6 处），是「找代码难」的主要来源。

## 目标

1. 按职责拆分，使每个文件聚焦单一目的、可独立理解
2. **行为零变化**：REST/JWT/公开 API/命名/算法不变；消费者 import 路径不变
3. 顺带用表驱动重构 `summarize_write_tool`（380 行 if 链 → 配置表），由既有测试兜底

## 决策

| 项 | 选择 |
|----|------|
| 范围 | 两个文件都拆 |
| 兼容策略 | 原模块保留聚合（薄 re-export / 编排入口），消费者不改 import |
| ai_tools 布局 | 子包 `app/services/ai/tools/`（read / write / skills / __init__），`ai_tools.py` 保留编排 |
| strategy_board 布局 | 平铺 `strategy_board_config.py` / `strategy_board_calc.py`，`strategy_board.py` 保留 `load_strategy_board` 入口 |
| summarize_write_tool | 重构为 mapping 表驱动（保留既有行为） |

## 组件设计

### `ai_tools.py`（844 → 编排 ~120 行）

| 新文件 | 内容 | 来源行 |
|--------|------|--------|
| `tools/__init__.py` | 聚合 re-export：`TOOL_HANDLERS`、`WRITE_HANDLERS`、`TOOL_DEFINITIONS`、`WRITE_TOOL_NAMES`、`MAX_RESULT_CHARS`、`summarize_write_tool` 等（供 `ai_agent.py` 等 `from app.services.ai.tools import ...`） | 壳 |
| `tools/_common.py` | `MAX_RESULT_CHARS`、`ToolHandler`、`_truncate`、`_parse_args`、`_mcp_tool_definitions` | 22/40/751/785 |
| `tools/read.py` | 14 个 `_get_*` 只读工具 + `TOOL_HANDLERS`（只读部分 12 条）+ 对应 `TOOL_DEFINITIONS` 条目 | 47-173 |
| `tools/skills.py` | `_list_skills`/`_read_skill`/`_run_skill` + 对应定义 | 173-200 |
| `tools/write.py` | 8 个 `_add_*`/`_upsert_*`/`_delete_*` + `WRITE_HANDLERS` + `WRITE_TOOL_NAMES` + `summarize_write_tool`（表驱动） | 201-750 |

`ai_tools.py` 保留：`execute_tool`、`execute_write_tool`、`get_tool_definitions` 编排入口，从 `tools/` 子模块聚合 handler 表与定义。`TOOL_HANDLERS` / `WRITE_HANDLERS` 组装为「read + skills + write」合并字典（原文件即是全量）。

**`summarize_write_tool` 表驱动重构**（`tools/write.py`）：

```python
def _sym(args: dict[str, Any]) -> str:
    return str(args.get("symbol") or args.get("vt_symbol") or "").strip() or "?"

def _preview(raw: Any, limit: int = 40) -> str:
    body = str(raw or "").strip().replace("\n", " ")
    return body[:limit] + ("…" if len(body) > limit else "")

_WRITE_SUMMARIES: dict[str, Callable[[dict[str, Any]], str]] = {
    "add_watchlist": lambda a: f"加自选：{_sym(a)}" + (f"（{a.get('name', '').strip()}）" if a.get("name", "").strip() else ""),
    "remove_watchlist": lambda a: f"删自选：{_sym(a)}",
    "upsert_note_memo": lambda a: f"写备忘：{_sym(a)} — {_preview(a.get('body'))}",
    "add_note_entry": lambda a: f"记流水：{_sym(a)} — {_preview(a.get('body'))}",
    "upsert_position": lambda a: f"录入/更新持仓：{_sym(a)} 成本{a.get('cost_price')} 数量{a.get('volume')}",
    "delete_position": lambda a: f"删除持仓：{_sym(a)}",
    "add_signal_panel": lambda a: f"加入信号名单：{_sym(a)}",
    "remove_signal_panel": lambda a: f"移出信号名单：{_sym(a)}",
}

def summarize_write_tool(name: str, args: dict[str, Any]) -> str:
    summary = _WRITE_SUMMARIES.get(name)
    return summary(args) if summary else name
```

行为与原实现逐一等价（原 `if` 链逐分支核对；`name` 无匹配时返回 `name` 保留）。

### `strategy_board.py`（609 → 入口 ~200 行）

| 新文件 | 内容 | 来源行 |
|--------|------|--------|
| `strategy_board_config.py` | `DEFAULT_CONFIG_KEY`、`SIGNAL_MODE_*`、`ALL_SIGNAL_MODES`、`DEFAULT_DOUBLE_MA_*`、`BAR_LIMIT`、`bars_limit_for`、`resolve_config_key`、`double_ma_config_key`…`atr_breakout_config_key`、`resolve_board_config_key`、`_pref_fast_slow` | 26-254 |
| `strategy_board_calc.py` | `_safe_float`、`_parse_payload`、`_load_daily_bars_map`、`_compute_snapshot`、`_t1_locked`、`_signal_label`、`enrich_position_risk`、`_pack_signal_row` | 79-407 |

`strategy_board.py` 保留：`load_strategy_board` 主入口 + `_mode_note`，从 `_config`/`_calc` 子模块 import 常量与内部函数。

**注意依赖**：`strategy_board_config.py` 不依赖 `_calc`；`_calc` 依赖 `_config`（`SIGNAL_MODE_*`、`resolve_config_key`）；`strategy_board.py` 依赖两者——按此顺序拆可避免循环导入。`enrich_position_risk` 等被 `_calc` 内部与 `load_strategy_board` 使用的函数归入 `_calc`。

## 数据流 / 错误处理

- 无行为变化：拆分是纯结构移动 + 聚合，无新增逻辑路径
- 表驱动重构依赖既有 `test_ai_proposals.py::test_summarize_write_tool`、`test_ai_write_positions.py` 兜底（已覆盖 8 个工具前缀 + 未知名回退）

## 测试

| 类型 | 用例 |
|------|------|
| 回归 | 全量 pytest 绿（当前 main 上 718 passed, 12 skipped） |
| 行为 | `summarize_write_tool` 既有测试原样通过（含前缀断言与 `upsert_position` 成本/数量） |
| 冒烟 | `import app.main`、`from app.services.ai import ai_tools`、`from app.services.strategy import strategy_board` 均可用 |
| 兼容 | 消费者 import 路径不变（`app.services.ai.ai_tools`、`app.services.strategy.strategy_board`） |

## 验收

- `ai_tools.py` ≤ ~150 行（编排）；`strategy_board.py` ≤ ~250 行（入口）
- 全量测试绿；既有 import 路径全部可用
- 表驱动 `summarize_write_tool` 与 if 链行为逐分支等价（有测试断言）
- 零逻辑改动（diff 为移动/聚合/重构，无新增行为）

## 非目标

- 重构各工具 handler 内部实现（保留原样迁入）
- 迁域（`services/ai`、`services/strategy` 不在 domains 拆分范围内）
- 拆 `ai_read_tools.py`（172 行，尚可）与其他文件
- `TOOL_DEFINITIONS` JSON schema 调整（保留逐字）

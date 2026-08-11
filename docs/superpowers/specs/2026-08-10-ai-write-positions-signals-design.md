# AI 写工具：持仓 + 信号名单 设计

日期：2026-08-10  
状态：已批准（方案 1：扩展 `ai_tools`；缺自选时持仓失败，与 Web 一致）  
范围：仅 zak2；不改 zak；不 import vnpy_*

## 目标

1. Agent 可通过确认卡提议：**录入/更新/删除持仓**、**加入/移出信号名单**。  
2. 落库走现有 `positions_repo` / `signal_panel_repo`，校验与 Web API 一致。  
3. 复用现有 proposal + SSE `confirm_required` + `AiView` 确认卡，不改确认基建。

## 非目标

- 守则计划页增强 / 计划激活编辑  
- Docker、下单、行情采集进 API  
- 只读工具 `get_positions` / `get_signal_panel`（可另刀）  
- 缺自选时自动加自选或复合 proposal  
- 改 confirmation UI / proposal 存储（仍进程内 dict）  
- MCP 写操作、桌面 skill registry

## 写工具

全部加入 `WRITE_TOOL_NAMES`；模型调用只建 proposal，确认后 `execute_write_tool`。

| 工具 | 必填 | 可选 | 行为 |
|------|------|------|------|
| `upsert_position` | `symbol`（或 `vt_symbol`）、`cost_price`、`volume`、`buy_date` | `notes`、`plan_pct`、`exchange` | 已有持仓 → `update_position`；否则 `add_position`。**不在自选 → `{error}`**（文案含「须先加入自选」）。整手、上限 20 等同 repo。 |
| `delete_position` | `symbol`（或 `vt_symbol`） | `exchange` | `delete_position`；无记录 → error |
| `add_signal_panel` | `symbol`（或 `vt_symbol`） | `exchange` | `signal_panel_repo.add_symbol`；已在名单幂等返回 ok；满 10 → error |
| `remove_signal_panel` | `symbol`（或 `vt_symbol`） | `exchange` | `remove_symbol`；不在名单 → error（与 Web 404 一致） |

`upsert_position` 合并 add/update，避免模型二选一。

### 摘要（确认卡）

- `录入持仓：{vt} 成本{cost} 数量{vol}`（update 可用「更新持仓」或同句；实现统一「录入/更新持仓：…」亦可）  
- `删除持仓：{vt}`  
- `加入信号名单：{vt}`  
- `移出信号名单：{vt}`

### 错误

repo / FastAPI `HTTPException` → 与现有写工具相同，返回 `{error: detail}`，不抛穿确认路径外未捕获异常。

## 模块

| 路径 | 职责 |
|------|------|
| `backend/app/services/ai_tools.py` | 增 4 个 write handler、definitions、summarize、WRITE 集合 |
| `positions_repo` / `signal_panel_repo` | 只复用，不改语义 |
| `ai_agent` / `ai_proposals` / `AiView` | 不改（已按 WRITE 集合拦截） |
| `tests/test_ai_tools.py`、`test_ai_proposals.py` | 更新写工具集合断言 |
| 新建或扩测 `tests/test_ai_write_positions.py`（名可调整） | mock repo：upsert 缺自选 / 成功分支、delete、信号 add/remove |

## 流程

与既有写确认一致：

1. 模型调写工具 → `create_proposal`（不写库）  
2. SSE `confirm_required`  
3. 用户 confirm → `execute_write_tool` → repo  
4. reject → 失效 proposal  

## 文档

- `docs/gap-vs-desktop.md`：写工具行改为含持仓 CRUD（upsert+delete）与信号名单增删；流式 chat 行补持仓/信号  
- 「建议下一刀」：去掉 Docker 若仍写着则改「只读持仓/信号工具或其它」；本刀不绑 Docker  
- `docs/smoke-checklist.md`：Ai 可提议持仓/信号并确认卡落库（可注明 pytest 覆盖）

## 验收

1. 新写工具均在 `WRITE_TOOL_NAMES`；`execute_tool` 直接调用返回须确认错误  
2. mock：缺自选 upsert 失败；有自选可 add；已有可 update；delete / 信号增删符合 repo 语义  
3. 集合断言与相关 pytest 绿；前端无改则可不强制 build  

## 澄清记录

- 方案：扩展 `ai_tools`，不新建写模块、不走内部 HTTP  
- 缺自选：失败，须先 `add_watchlist` 确认  
- 工具集：全量（upsert/delete 持仓 + 信号 add/remove）  
